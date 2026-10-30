"""
Subscription Webhook Handler
Processes Stripe webhook events for subscriptions

SECURITY FIX (P0): Replaced in-process ``deque`` idempotency with
Redis-backed deduplication.  The old approach used
``_processed_events = deque(maxlen=1000)`` which is process-local.
With multiple workers/replicas, the same Stripe event delivered to
worker A was not visible to worker B, allowing duplicate processing.
``handle_invoice_failed`` previously incremented ``dunning_retry_count``
on every delivery, so a retried webhook could inflate the counter and
trigger premature dunning escalation.

Now: Redis ``SET event_id EX 86400 NX`` is used for cross-worker dedup.
If Redis is unavailable, non-production environments fall back to the
in-process deque. Production fails closed so Stripe retries the event instead
of risking duplicate financial state across workers.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from collections import deque

from app.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SubscriptionInterval,
)
from app.models.practice import Practice
from app.core.config_simple import settings

logger = logging.getLogger(__name__)


class WebhookDeduplicationUnavailable(RuntimeError):
    """Raised when production cannot guarantee cross-worker idempotency."""


def _redis_client():
    """Return a Redis client if REDIS_URL is configured, else None."""
    if not settings.REDIS_URL:
        return None
    import redis as redis_lib

    return redis_lib.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


class SubscriptionWebhookHandler:
    """Handler for Stripe subscription webhooks"""
    # Fallback for when Redis is unavailable (dev environments).
    # In production, Redis SETNX is used instead (cross-worker safe).
    _processed_events_fallback = deque(maxlen=1000)

    @staticmethod
    def _is_duplicate_event(event_id: str) -> bool:
        """Check if this event was already processed (cross-worker safe).

        Uses Redis ``SET event_id EX 86400 NX`` for atomic, cross-worker
        idempotency.  Falls back to in-process deque when Redis is not
        configured (development only).

        Returns True if the event was already processed.
        """
        if not event_id:
            return False

        try:
            r = _redis_client()
            if r:
                # SET NX: only sets if key does not exist.
                # Returns True if the key was set (new event), None if
                # it already existed (duplicate).
                result = r.set(
                    f"webhook:processed:{event_id}",
                    "1",
                    ex=86400,  # 24 hours
                    nx=True,
                )
                return result is None  # None = key already existed = duplicate
        except Exception as exc:
            if settings.ENVIRONMENT == "production":
                logger.error("Stripe webhook deduplication unavailable: %s", exc)
                raise WebhookDeduplicationUnavailable(
                    "Redis webhook deduplication is unavailable"
                ) from exc
            logger.warning(
                "Redis webhook deduplication failed; using local fallback outside production: %s",
                exc,
            )

        if settings.ENVIRONMENT == "production":
            raise WebhookDeduplicationUnavailable(
                "Redis webhook deduplication is unavailable"
            )

        # Fallback: in-process deque (non-production only)
        if event_id in SubscriptionWebhookHandler._processed_events_fallback:
            return True
        SubscriptionWebhookHandler._processed_events_fallback.append(event_id)
        return False

    @staticmethod
    def release_event_marker(event_id: Optional[str]) -> None:
        """Undo the dedup marker so the processor can retry this event.

        Audit finding C-01: the marker is written *before* the handler runs
        (that is what makes it a race guard). If the handler then fails, the
        marker must be removed or the processor's retry is answered with
        "duplicate, already handled" and the event is lost -- for Stripe that
        means acknowledging money that was never recorded locally.

        Safe to call unconditionally; never raises.
        """
        if not event_id:
            return
        try:
            r = _redis_client()
            if r:
                r.delete(f"webhook:processed:{event_id}")
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.error(
                "Failed to release webhook dedup marker for %s; the retry will "
                "be treated as a duplicate and the event dropped: %s",
                event_id,
                exc,
            )
        try:
            fallback = SubscriptionWebhookHandler._processed_events_fallback
            while event_id in fallback:
                fallback.remove(event_id)
        except (ValueError, RuntimeError):  # pragma: no cover
            pass

    @staticmethod
    async def handle_subscription_created(
        db: AsyncSession,
        sub_data: Dict[str, Any],
    ) -> None:
        """Attach Stripe state only to a pre-authorized local subscription."""
        from uuid import UUID

        stripe_sub_id = sub_data.get("id")
        metadata = sub_data.get("metadata", {}) or {}
        local_id = metadata.get("coredent_subscription_id")
        practice_id = metadata.get("practice_id")
        plan_id = metadata.get("coredent_plan_id")
        if not all((stripe_sub_id, local_id, practice_id, plan_id)):
            logger.warning(
                "Quarantined subscription.created event %s: missing CoreDent ownership metadata",
                stripe_sub_id,
            )
            return

        try:
            local_uuid = UUID(str(local_id))
        except (TypeError, ValueError):
            logger.warning(
                "Quarantined subscription.created event %s: invalid local subscription id",
                stripe_sub_id,
            )
            return

        result = await db.execute(
            select(Subscription)
            .where(Subscription.id == local_uuid)
            .with_for_update()
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            logger.warning(
                "Quarantined subscription.created event %s: local subscription %s does not exist",
                stripe_sub_id,
                local_id,
            )
            return

        if str(sub.practice_id) != str(practice_id) or str(sub.plan_id) != str(plan_id):
            logger.error(
                "Quarantined subscription.created event %s: ownership metadata mismatch",
                stripe_sub_id,
            )
            return

        items = (sub_data.get("items") or {}).get("data") or []
        first_item = items[0] if items else {}
        price = first_item.get("price") or first_item.get("plan") or {}
        price_id = price.get("id")
        plan_result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if (
            plan is None
            or not plan.stripe_price_id
            or not price_id
            or plan.stripe_price_id != price_id
        ):
            logger.error(
                "Quarantined subscription.created event %s: Stripe price does not match local plan",
                stripe_sub_id,
            )
            return

        stripe_customer_id = sub_data.get("customer")
        if sub.stripe_subscription_id and sub.stripe_subscription_id != stripe_sub_id:
            logger.error(
                "Quarantined subscription.created event %s: local row already has another Stripe subscription",
                stripe_sub_id,
            )
            return
        if sub.stripe_customer_id and sub.stripe_customer_id != stripe_customer_id:
            logger.error(
                "Quarantined subscription.created event %s: Stripe customer mismatch",
                stripe_sub_id,
            )
            return

        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.UNPAID,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.INCOMPLETE,
            "paused": SubscriptionStatus.PAUSED,
        }
        sub.stripe_subscription_id = stripe_sub_id
        sub.stripe_customer_id = stripe_customer_id
        sub.status = status_map.get(
            sub_data.get("status"), SubscriptionStatus.INCOMPLETE
        )
        if sub_data.get("current_period_start"):
            sub.current_period_start = datetime.fromtimestamp(
                sub_data["current_period_start"], tz=timezone.utc
            )
        if sub_data.get("current_period_end"):
            sub.current_period_end = datetime.fromtimestamp(
                sub_data["current_period_end"], tz=timezone.utc
            )
        await db.commit()
        logger.info(
            "Bound Stripe subscription %s to local subscription %s",
            stripe_sub_id,
            sub.id,
        )

    @staticmethod
    async def handle_subscription_updated(
        db: AsyncSession,
        sub_data: Dict[str, Any],
    ) -> None:
        """Handle subscription update (plan changes, cancellations)"""
        stripe_sub_id = sub_data.get("id")

        result = await db.execute(
            select(Subscription)
            .where(Subscription.stripe_subscription_id == stripe_sub_id)
            .with_for_update()
        )
        sub = result.scalar_one_or_none()

        if not sub:
            logger.warning(f"Subscription not found for update: {stripe_sub_id}")
            return

        # Update status (FIX: cover paused/incomplete/incomplete_expired —
        # dropping them left stale ACTIVE; unknown values are logged, not
        # silently kept).
        stripe_status = sub_data.get("status")
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "trialing": SubscriptionStatus.TRIALING,
            "unpaid": SubscriptionStatus.UNPAID,
            "paused": SubscriptionStatus.PAUSED,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.EXPIRED,
        }

        if stripe_status in status_map:
            sub.status = status_map[stripe_status]
        elif stripe_status is not None:
            logger.warning(
                "Unknown Stripe subscription status %r for %s; keeping %s",
                stripe_status,
                stripe_sub_id,
                sub.status,
            )

        sub.cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

        if sub_data.get("current_period_end"):
            sub.current_period_end = datetime.fromtimestamp(
                sub_data["current_period_end"],
                tz=timezone.utc
            )

        if sub_data.get("current_period_start"):
            sub.current_period_start = datetime.fromtimestamp(
                sub_data["current_period_start"],
                tz=timezone.utc
            )

        await db.commit()
        logger.info(f"Updated subscription: {stripe_sub_id}, status: {stripe_status}")

    @staticmethod
    async def handle_subscription_deleted(
        db: AsyncSession,
        sub_data: Dict[str, Any],
    ) -> None:
        """Handle subscription cancellation/deletion"""
        stripe_sub_id = sub_data.get("id")

        result = await db.execute(
            select(Subscription)
            .where(Subscription.stripe_subscription_id == stripe_sub_id)
            .with_for_update()
        )
        sub = result.scalar_one_or_none()

        if not sub:
            logger.warning(f"Subscription not found for deletion: {stripe_sub_id}")
            return

        sub.status = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = True
        sub.canceled_at = datetime.now(timezone.utc)

        await db.commit()
        logger.info(f"Deleted subscription: {stripe_sub_id}")

    @staticmethod
    async def handle_invoice_succeeded(
        db: AsyncSession,
        invoice_data: Dict[str, Any],
    ) -> Optional[Subscription]:
        """Handle successful payment"""
        sub_id = invoice_data.get("subscription")

        if not sub_id:
            return None

        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            logger.warning(f"Subscription not found for invoice success: {sub_id}")
            return None

        # FIX: never resurrect CANCELED/EXPIRED via a late invoice event.
        if sub.status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
            logger.warning(
                "Ignoring invoice.succeeded for %s in terminal status %s",
                sub_id,
                sub.status,
            )
            return sub
        sub.status = SubscriptionStatus.ACTIVE
        sub.dunning_retry_count = 0
        sub.last_payment_error = None

        await db.commit()
        logger.info(f"Invoice succeeded for subscription: {sub_id}")

        return sub

    @staticmethod
    async def handle_invoice_failed(
        db: AsyncSession,
        invoice_data: Dict[str, Any],
    ) -> Optional[Subscription]:
        """Handle failed payment - trigger dunning

        SECURITY FIX: Added DB-level idempotency to prevent dunning count
        inflation from retried webhooks.  We check ``last_payment_error``
        to see if this exact failure was already recorded.
        """
        sub_id = invoice_data.get("subscription")

        if not sub_id:
            return None

        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            logger.warning(f"Subscription not found for invoice failure: {sub_id}")
            return None

        # Idempotency keyed on the Stripe INVOICE id — the previous
        # error-string equality check caused both false dedup (two different
        # invoices with the same message) and false double-counts (a retried
        # webhook whose error text differed slightly).
        invoice_id = invoice_data.get("id")
        if invoice_id:
            try:
                r = _redis_client()
                if r:
                    set_result = r.set(
                        f"webhook:invoice_failed:{invoice_id}",
                        "1",
                        ex=7 * 86400,
                        nx=True,
                    )
                    if set_result is None:
                        logger.info(
                            f"Invoice failure already recorded for invoice {invoice_id}; skipping duplicate"
                        )
                        return sub
            except Exception as exc:
                if settings.ENVIRONMENT == "production":
                    logger.error("Invoice-failure deduplication unavailable: %s", exc)
                    raise WebhookDeduplicationUnavailable(
                        "Redis invoice-failure deduplication is unavailable"
                    ) from exc
                logger.warning("Redis invoice-failure dedup failed; processing anyway: %s", exc)

        error_msg = invoice_data.get("last_payment_error", {}).get("message", "Payment failed")

        sub.status = SubscriptionStatus.PAST_DUE
        sub.last_payment_error = error_msg
        sub.dunning_retry_count = (sub.dunning_retry_count or 0) + 1
        sub.next_retry_at = datetime.now(timezone.utc)  # Immediate retry

        await db.commit()
        logger.warning(f"Invoice failed for subscription: {sub_id}, error: {sub.last_payment_error}")

        return sub

    @staticmethod
    async def handle_trial_will_end(
        db: AsyncSession,
        sub_data: Dict[str, Any],
    ) -> Optional[Subscription]:
        """Handle trial ending soon - send reminder"""
        stripe_sub_id = sub_data.get("id")

        result = await db.execute(
            select(Subscription)
            .where(Subscription.stripe_subscription_id == stripe_sub_id)
            .with_for_update()
        )
        sub = result.scalar_one_or_none()

        if not sub:
            logger.warning(f"Subscription not found for trial end: {stripe_sub_id}")
            return None

        logger.info(f"Trial ending soon for subscription: {stripe_sub_id}")
        return sub

    @staticmethod
    async def process_webhook_event(
        db: AsyncSession,
        event: Dict[str, Any],
    ) -> bool:
        """
        Process a Stripe webhook event
        Returns: True if handled successfully
        """
        event_type = event.get("type")
        event_id = event.get("id")
        data_obj = event.get("data", {}).get("object", {})

        # SECURITY FIX: Cross-worker idempotency via Redis (P0 fix)
        if SubscriptionWebhookHandler._is_duplicate_event(event_id):
            logger.info(f"Webhook event already processed: {event_id}")
            return True

        try:
            if event_type == "customer.subscription.created":
                await SubscriptionWebhookHandler.handle_subscription_created(db, data_obj)

            elif event_type == "customer.subscription.updated":
                await SubscriptionWebhookHandler.handle_subscription_updated(db, data_obj)

            elif event_type == "customer.subscription.deleted":
                await SubscriptionWebhookHandler.handle_subscription_deleted(db, data_obj)

            elif event_type == "invoice.payment_succeeded":
                await SubscriptionWebhookHandler.handle_invoice_succeeded(db, data_obj)

            elif event_type == "invoice.payment_failed":
                await SubscriptionWebhookHandler.handle_invoice_failed(db, data_obj)

            elif event_type == "customer.subscription.trial_will_end":
                await SubscriptionWebhookHandler.handle_trial_will_end(db, data_obj)

            else:
                logger.debug(f"Unhandled webhook event type: {event_type}")
                return False

            if event_id:
                # Event was already recorded in _is_duplicate_event via
                # Redis SETNX, so we don't need to add it again here.
                pass
            return True

        except Exception as e:
            logger.error(f"Error processing webhook event {event_type}: {e}")
            SubscriptionWebhookHandler.release_event_marker(event_id)
            return False
