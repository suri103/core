"""
Stripe Payment Processing Endpoints
Handles payment intents, subscriptions, and webhooks
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import asyncio
import contextvars
from datetime import datetime, timezone
from decimal import Decimal
import logging

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.api.deps import get_db, get_current_active_user, require_role, verify_csrf
from app.core.database import row_locks_supported
from app.models.user import User, UserRole
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.payment import PaymentIntentCreate, PaymentIntentResponse
from app.schemas.subscription import SubscriptionCreate
from app.core.config_simple import settings
from app.core.email import send_payment_confirmation_email

logger = logging.getLogger(__name__)

# The id of the processor event currently being dispatched. Handlers use it to
# write the durable ``processor_webhook_events`` row without every handler
# signature having to thread it through.
_current_event_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "stripe_current_event_id", default=None
)

# Map Stripe status strings to our SubscriptionStatus enum.
# Stripe can send statuses like "incomplete_expired" or "paused" that have
# no enum member; we fall back to INCOMPLETE so the insert never crashes.
_STRIPE_STATUS_MAP: Dict[str, SubscriptionStatus] = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.UNPAID,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.INCOMPLETE,
    "paused": SubscriptionStatus.PAUSED,
}

# Map Stripe plan interval strings to our SubscriptionInterval enum.
# L-7 FIX / L-5 CLEANUP: "day" (daily billing) is intentionally unsupported —
# the SubscriptionInterval enum has no DAILY and Subscription.interval is NOT
# NULL, so storing None would crash or mis-bill. This map was previously dead
# code in this module (the live webhook path resolves intervals in
# subscriptions.py, which maps our enum values to Stripe interval strings at
# creation time); it has been removed. If daily support is ever wired, add
# DAILY to the enum + a migration, and extend the interval maps in
# subscriptions.py — never None-map an unsupported value.

router = APIRouter()

# F10 FIX: Fail fast at import if Stripe key is missing in production.
# Previously the app would boot and only fail on the first Stripe API call,
# making misconfiguration hard to diagnose.
if settings.ENVIRONMENT == "production" and not settings.STRIPE_SECRET_KEY:
    raise RuntimeError(
        "STRIPE_SECRET_KEY is not configured. Stripe payment endpoints "
        "cannot operate without it. Set STRIPE_SECRET_KEY in the environment."
    )

# Initialize Stripe (deferred key set so dev/test can boot without it)
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/create-payment-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    payment_data: PaymentIntentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf)
):
    """Fail closed until payment persistence and reconciliation are idempotent."""
    del payment_data, db, current_user
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Online payment processing is temporarily unavailable. "
            "No payment was created."
        ),
    )


@router.post("/create-subscription", response_model=Dict[str, Any])
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf)
):
    """Deprecated orphan-subscription path; use the tenant-owned API."""
    del subscription_data, db, current_user
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Use POST /api/v1/subscriptions/ so ownership is recorded before Stripe creation",
    )
@router.get("/subscription/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
):
    """
    Get subscription details from Stripe
    """
    try:
        local_result = await db.execute(
            select(Subscription.practice_id).where(
                Subscription.stripe_subscription_id == subscription_id,
            )
        )
        local_practice_id = local_result.scalar_one_or_none()
        if local_practice_id is not None and local_practice_id != current_user.practice_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this subscription",
            )
        subscription = await asyncio.to_thread(
            stripe.Subscription.retrieve,
            subscription_id,
            expand=["items.data.price.product"]
        )

        metadata_practice = (subscription.metadata or {}).get("practice_id")
        if (
            local_practice_id is None and str(metadata_practice) != str(current_user.practice_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this subscription",
            )

        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            "items": [
                {
                    "price_id": item.price.id,
                    "product_name": item.price.product.name if isinstance(item.price.product, stripe.Product) else item.price.product,
                    "quantity": item.quantity
                }
                for item in subscription.items.data
            ],
            "cancel_at_period_end": subscription.cancel_at_period_end
        }

    # Stripe SDK exposes the exceptions submodule lazily; runtime-verified.
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"Failed to retrieve subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve subscription: {str(e)}"
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Failed to retrieve subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription"
        )


@router.post("/cancel-subscription/{subscription_id}")
async def cancel_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf)
):
    """
    Cancel a Stripe subscription
    """
    try:
        subscription = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)

        local_result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id,
                Subscription.practice_id == current_user.practice_id,
            )
        )
        local_subscription = local_result.scalar_one_or_none()
        metadata_practice = (subscription.metadata or {}).get("practice_id")
        if (
            local_subscription is None
            and str(metadata_practice) != str(current_user.practice_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this subscription",
            )

        # F8 FIX: Use cancel_at_period_end=True instead of immediate delete.
        # Immediate cancellation revokes access instantly even though the
        # customer has already paid for the current period. cancel_at_period_end
        # lets them keep access until the period ends, which is the expected
        # SaaS behavior. The webhook handler will set CANCELED when the period
        # actually ends.
        canceled = await asyncio.to_thread(
            stripe.Subscription.modify,
            subscription_id,
            cancel_at_period_end=True,
        )

        # Update local subscription record
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id,
                Subscription.practice_id == current_user.practice_id,
            )
        )
        local_subscription = result.scalar_one_or_none()

        if local_subscription:
            # Keep access active until Stripe confirms the period has ended.
            local_subscription.cancel_at_period_end = True
            await db.commit()

        return {
            "id": canceled.id,
            "status": canceled.status,
            "canceled_at": datetime.fromtimestamp(canceled.canceled_at, tz=timezone.utc) if canceled.canceled_at else None
        }

    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel subscription: {str(e)}"
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhooks with enhanced security
    
    Security layers:
    1. IP whitelist verification (Stripe IPs only)
    2. Stripe signature verification
    3. Rate limiting (handled by middleware)
    4. Comprehensive logging
    """
    from app.core.webhook_security import log_webhook_attempt

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # SECURITY FIX: Use the hardened webhook_security module for signature
    # verification (constant-time comparison, configurable tolerance,
    # fail-closed if secret is empty) instead of the Stripe SDK directly.
    try:
        from app.core.webhook_security import construct_stripe_event
        event = construct_stripe_event(payload, sig_header)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        log_webhook_attempt(request, "stripe", False, str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Idempotency check: deduplicate webhook event IDs (Redis SETNX / fallback).
    # The marker is written BEFORE the handler runs so concurrent deliveries
    # cannot both process the event. That means every failure path below MUST
    # release the marker, or Stripe's retry is answered "already handled".
    event_id = event.get("id")
    from app.services.subscription_webhooks import (
        SubscriptionWebhookHandler,
        WebhookDeduplicationUnavailable,
    )

    try:
        is_duplicate = bool(event_id) and SubscriptionWebhookHandler._is_duplicate_event(event_id)
    except WebhookDeduplicationUnavailable as exc:
        # Fail closed: without cross-worker dedup we cannot guarantee we won't
        # double-apply financial state. 503 makes Stripe retry.
        logger.error("Stripe webhook rejected, deduplication unavailable: %s", exc)
        log_webhook_attempt(request, "stripe", False, "deduplication unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook processing temporarily unavailable; please retry.",
        )

    if is_duplicate:
        logger.info(f"Duplicate Stripe webhook event ignored: {event_id}")
        return JSONResponse(status_code=200, content={"ok": True, "duplicate": True})

    # C-01 FIX: dispatch inside a guard that releases the dedup marker on
    # failure. Previously a handler exception propagated with the marker still
    # set, so the retry short-circuited as a duplicate and a successful Stripe
    # payment could be acknowledged with nothing recorded locally.
    try:
        _current_event_id.set(event_id)
        # Handle the event
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            await handle_payment_succeeded(db, payment_intent)

        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            await handle_payment_failed(db, payment_intent)

        elif event["type"] == "charge.refunded":
            charge = event["data"]["object"]
            await handle_charge_refunded(db, charge)

        elif event["type"] == "customer.subscription.created":
            subscription = event["data"]["object"]
            await SubscriptionWebhookHandler.handle_subscription_created(db, subscription)

        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            await SubscriptionWebhookHandler.handle_subscription_updated(db, subscription)

        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await SubscriptionWebhookHandler.handle_subscription_deleted(db, subscription)

        elif event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            await handle_invoice_paid(db, invoice)

        else:
            # Recorded for audit completeness so "we never saw it" and "we saw
            # it and chose not to act" are distinguishable during incidents.
            from app.services.processor_events import ProcessorEventStatus, record_event

            await record_event(
                db,
                processor="stripe",
                event_id=event_id,
                event_type=event["type"],
                payload=event.get("data", {}).get("object", {}) or {},
                status=ProcessorEventStatus.IGNORED,
            )
            await db.commit()

    except Exception as exc:
        SubscriptionWebhookHandler.release_event_marker(event_id)
        logger.exception(
            "Stripe webhook handler failed for event %s (%s); dedup marker "
            "released so the retry is reprocessed",
            event_id,
            event.get("type"),
        )
        log_webhook_attempt(request, "stripe", False, f"handler failed: {type(exc).__name__}")
        # Best-effort durable record of the failure. Must not mask the 500.
        try:
            await db.rollback()
            from app.services.processor_events import ProcessorEventStatus, record_event

            await record_event(
                db,
                processor="stripe",
                event_id=event_id,
                event_type=event.get("type", "unknown"),
                payload=event.get("data", {}).get("object", {}) or {},
                status=ProcessorEventStatus.FAILED,
                error_message=f"{type(exc).__name__}: {exc}"[:1000],
            )
            await db.commit()
        except Exception:  # noqa: BLE001 - never shadow the original failure
            logger.error("Could not persist failed-webhook record for %s", event_id)
        # 500 tells Stripe to retry with backoff. Never answer 200 for an
        # event we did not durably record.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook handler failed; the event will be retried.",
        )

    # Log successful webhook processing
    log_webhook_attempt(request, "stripe", True)

    return JSONResponse(status_code=200, content={"ok": True})


async def handle_payment_succeeded(db: AsyncSession, payment_intent: dict):
    """Record a successful payment, creating the ledger row if it is missing.

    C-01 FIX: this used to be update-only. When no ``PaymentTransaction``
    matched the incoming ``payment_intent`` it logged "Payment succeeded" and
    returned, and the endpoint answered 200 -- money acknowledged, nothing
    recorded. Now the row is created when it can be attributed to a tenant,
    and quarantined in ``processor_webhook_events`` when it cannot.
    """
    from app.models.payment import PaymentStatus as TxnStatus
    from app.services.processor_events import (
        ProcessorEventStatus,
        record_event,
        resolve_payment_transaction,
    )

    event_id = _current_event_id.get()
    try:
        payment, reason = await resolve_payment_transaction(db, payment_intent)

        if payment is None:
            # Money moved but we cannot attribute it. Persist the event so it
            # is visible and reconcilable, then acknowledge -- a retry cannot
            # supply the metadata that is missing.
            logger.critical(
                "UNRECONCILED PAYMENT: processor payment %s succeeded but "
                "could not be recorded (%s). Quarantined for reconciliation.",
                payment_intent.get("id"),
                reason,
            )
            await record_event(
                db,
                processor="stripe",
                event_id=event_id,
                event_type="payment_intent.succeeded",
                payload=payment_intent,
                status=ProcessorEventStatus.UNRECONCILED,
                error_message=reason,
            )
            await db.commit()
            return

        # H4 FIX: succeeded must not resurrect terminal refund/void states.
        if payment.status in (TxnStatus.REFUNDED, TxnStatus.PARTIALLY_REFUNDED, TxnStatus.VOIDED, TxnStatus.CANCELLED):
            logger.warning(
                "Ignoring payment_intent.succeeded for %s in terminal status %s",
                payment_intent.get("id"),
                payment.status,
            )
            await record_event(
                db,
                processor="stripe",
                event_id=event_id,
                event_type="payment_intent.succeeded",
                payload=payment_intent,
                status=ProcessorEventStatus.IGNORED,
                practice_id=payment.practice_id,
                payment_transaction_id=payment.id,
            )
            await db.commit()
            return

        already_completed = payment.status == TxnStatus.COMPLETED

        if not already_completed:
            payment.status = TxnStatus.COMPLETED
            payment.processed_at = datetime.now(timezone.utc)

        await record_event(
            db,
            processor="stripe",
            event_id=event_id,
            event_type="payment_intent.succeeded",
            payload=payment_intent,
            status=ProcessorEventStatus.PROCESSED,
            practice_id=payment.practice_id,
            payment_transaction_id=payment.id,
        )
        await db.commit()

        if already_completed:
            logger.info(
                "Duplicate payment_intent.succeeded ignored: %s",
                payment_intent.get("id"),
            )
            return

        # Confirmation email is best-effort and must never roll back the
        # ledger write above (which is already committed).
        recipient = payment_intent.get("customer_email") or payment_intent.get(
            "receipt_email"
        )
        if recipient:
            try:
                await send_payment_confirmation_email(
                    to_email=recipient,
                    amount=payment_intent["amount"] / 100,
                    currency=payment_intent["currency"],
                    payment_id=payment.id,
                    description=payment_intent.get("description", ""),
                )
            except Exception as email_exc:  # noqa: BLE001 - best effort
                logger.warning(
                    "Payment %s recorded but confirmation email failed: %s",
                    payment.id,
                    type(email_exc).__name__,
                )

        logger.info("Payment succeeded: %s", payment_intent.get("id"))
    except (ValueError, TypeError, KeyError, AttributeError, SQLAlchemyError) as e:
        logger.error(f"Error handling payment succeeded: {e}")
        await db.rollback()
        raise


async def handle_payment_failed(db: AsyncSession, payment_intent: dict):
    """Handle failed payment"""
    from app.models.payment import PaymentStatus as TxnStatus
    from app.services.processor_events import ProcessorEventStatus, record_event

    event_id = _current_event_id.get()
    try:
        from app.models.payment import PaymentTransaction
        result = await db.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.processor_transaction_id == payment_intent["id"]
            )
        )
        payment = result.scalar_one_or_none()

        if payment:
            # H4 FIX: COMPLETED->FAILED retroactive rewrite is forbidden (must
            # go through a refund); terminal REFUNDED must never flip. Only
            # pre-settlement states may fail.
            if payment.status in (TxnStatus.COMPLETED, TxnStatus.REFUNDED, TxnStatus.PARTIALLY_REFUNDED):
                logger.warning(
                    "Ignoring payment_failed for %s in terminal status %s; "
                    "refunds go through charge.refunded",
                    payment_intent.get("id"),
                    payment.status,
                )
            else:
                payment.status = TxnStatus.FAILED
                payment.error_message = payment_intent.get("last_payment_error", {}).get("message", "Unknown error")

        # A failure with no local row is not lost money, but it is still
        # recorded so support can correlate a customer's failed attempt.
        await record_event(
            db,
            processor="stripe",
            event_id=event_id,
            event_type="payment_intent.payment_failed",
            payload=payment_intent,
            status=ProcessorEventStatus.PROCESSED,
            practice_id=payment.practice_id if payment else None,
            payment_transaction_id=payment.id if payment else None,
        )
        await db.commit()

        logger.warning(f"Payment failed: {payment_intent['id']}")
    except (ValueError, TypeError, KeyError, AttributeError, SQLAlchemyError) as e:
        logger.error(f"Error handling payment failed: {e}")
        await db.rollback()
        raise


async def handle_charge_refunded(db: AsyncSession, charge: dict):
    """Record a processor-initiated refund against the local ledger.

    Without this, a refund issued from the Stripe dashboard never reached
    ``PaymentTransaction.refunded_amount``, so the local ledger kept counting
    refunded money as collected.

    M-1 FIX: the refund is now also propagated to the invoice-ledger
    ``Payment`` row that ``Invoice.amount_paid`` / billing summary / reports
    are computed from. Previously only the processor ledger
    (``PaymentTransaction``) was updated, so a Stripe-refunded charge left
    its invoice fully "paid" — overstating collections on every money
    surface — while the equivalent Razorpay webhook reconciled both
    ledgers. Propagation mirrors the Razorpay handler: link via
    ``PaymentTransaction.payment_id``, validate the amount, then let
    ``PaymentService.refresh_invoice_status`` re-derive the invoice status
    from the refund-aware ledger.
    """
    from app.models.payment import PaymentStatus as TxnStatus
    from app.services.processor_events import (
        ProcessorEventStatus,
        link_invoice_ledger_payment,
        minor_units_to_decimal,
        record_event,
    )
    from app.models.payment import PaymentTransaction
    # Both status enums are named PaymentStatus: the processor ledger
    # (payment_transactions) uses app.models.payment, the invoice ledger
    # (payments) uses app.models.billing. Alias them apart explicitly.
    from app.models.billing import Payment as InvoiceLedgerPayment
    from app.models.billing import PaymentStatus as InvoicePaymentStatus

    event_id = _current_event_id.get()
    try:
        processor_id = charge.get("payment_intent") or charge.get("id")
        result = await db.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.processor_transaction_id == processor_id
            )
        )
        payment = result.scalar_one_or_none()

        if payment is None:
            logger.critical(
                "UNRECONCILED REFUND: charge %s refunded but no local ledger "
                "row matches %s. Quarantined for reconciliation.",
                charge.get("id"),
                processor_id,
            )
            await record_event(
                db,
                processor="stripe",
                event_id=event_id,
                event_type="charge.refunded",
                payload=charge,
                status=ProcessorEventStatus.UNRECONCILED,
                error_message="no local PaymentTransaction for refunded charge",
            )
            await db.commit()
            return

        refunded = minor_units_to_decimal(
            charge.get("amount_refunded"), charge.get("currency")
        )
        payment.refunded_amount = refunded
        total = Decimal(str(payment.total_amount or payment.amount or 0))
        payment.status = (
            TxnStatus.REFUNDED if refunded >= total > 0 else TxnStatus.PARTIALLY_REFUNDED
        )

        # ── M-1: propagate to the invoice ledger ────────────────────────
        # Resolve the billing.Payment row for this processor charge. The
        # explicit FK link is preferred (link_invoice_ledger_payment fills
        # it when missing); manual ledger entries and unattributed charges
        # have no invoice-ledger row, and that is not an error.
        await link_invoice_ledger_payment(db, payment)
        ledger_payment = None
        if payment.payment_id is not None:
            ledger_result = await db.execute(
                select(InvoiceLedgerPayment).where(
                    InvoiceLedgerPayment.id == payment.payment_id,
                    InvoiceLedgerPayment.practice_id == payment.practice_id,
                )
            )
            ledger_payment = ledger_result.scalar_one_or_none()

        if ledger_payment is None:
            logger.info(
                "Refund for processor payment %s has no invoice-ledger row; "
                "processor ledger updated only.",
                payment.id,
            )
        elif not (Decimal("0") < refunded <= Decimal(str(ledger_payment.amount))):
            # PRODUCT DECISION (safe default): never write an invalid refund
            # (zero, negative, or larger than the recorded payment) into the
            # invoice ledger — a refund exceeding the ledger amount would push
            # amount_paid negative and corrupt balance_due plus every
            # downstream report. The processor ledger above keeps the
            # processor-reported value; the /billing/reconciliation report
            # surfaces the mismatch for an operator instead of guessing.
            logger.critical(
                "REFUND PROPAGATION SKIPPED for payment %s: processor reports "
                "cumulative refund %s against invoice-ledger amount %s; "
                "left for operator reconciliation.",
                payment.id,
                refunded,
                ledger_payment.amount,
            )
        else:
            ledger_payment.refunded_amount = refunded
            if refunded >= Decimal(str(ledger_payment.amount)):
                ledger_payment.status = InvoicePaymentStatus.REFUNDED
            else:
                ledger_payment.status = InvoicePaymentStatus.PARTIALLY_REFUNDED
            if ledger_payment.invoice_id is not None:
                from app.services.payment_service import PaymentService

                await PaymentService.refresh_invoice_status(
                    db,
                    ledger_payment.invoice_id,
                    ledger_payment.practice_id,
                )

        await record_event(
            db,
            processor="stripe",
            event_id=event_id,
            event_type="charge.refunded",
            payload=charge,
            status=ProcessorEventStatus.PROCESSED,
            practice_id=payment.practice_id,
            payment_transaction_id=payment.id,
        )
        await db.commit()
        logger.info("Refund recorded for payment %s: %s", payment.id, refunded)
    except (ValueError, TypeError, KeyError, AttributeError, SQLAlchemyError) as e:
        logger.error(f"Error handling charge refunded: {e}")
        await db.rollback()
        raise


async def handle_subscription_created(db: AsyncSession, subscription: dict):
    """Delegate creation events to the local-UUID ownership gate."""
    from app.services.subscription_webhooks import SubscriptionWebhookHandler

    await SubscriptionWebhookHandler.handle_subscription_created(db, subscription)


async def handle_subscription_updated(db: AsyncSession, subscription: dict):
    """Handle subscription update"""
    try:
        # M-1 FIX: take a row lock on the Subscription so concurrent Stripe
        # webhooks (e.g. customer.subscription.updated and
        # invoice.payment_succeeded racing on the same row) serialize and
        # neither overwrites the other's writes.
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == subscription["id"]
        )
        if row_locks_supported():
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub:
            # Map Stripe status safely via enum lookup
            new_status = _STRIPE_STATUS_MAP.get(subscription.get("status"))
            if new_status:
                sub.status = new_status
            sub.cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            if subscription.get("current_period_start"):
                sub.current_period_start = datetime.fromtimestamp(subscription["current_period_start"], tz=timezone.utc)
            if subscription.get("current_period_end"):
                sub.current_period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=timezone.utc)
            await db.commit()

        logger.info(f"Subscription updated: {subscription['id']}")
    except (IntegrityError, ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(f"Error handling subscription updated: {e}")
        await db.rollback()
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error handling subscription updated: {e}")
        await db.rollback()
        raise


async def handle_subscription_deleted(db: AsyncSession, subscription: dict):
    """Handle subscription cancellation"""
    try:
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == subscription["id"]
        )
        if row_locks_supported():
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(f"Subscription deleted: {subscription['id']}")
    except (IntegrityError, ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(f"Error handling subscription deleted: {e}")
        await db.rollback()
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error handling subscription deleted: {e}")
        await db.rollback()
        raise


async def handle_invoice_paid(db: AsyncSession, invoice: dict):
    """Handle successful invoice payment"""
    try:
        # This is for recurring subscription payments
        subscription_id = invoice.get("subscription")
        if subscription_id:
            stmt = select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
            if row_locks_supported():
                stmt = stmt.with_for_update()
            result = await db.execute(stmt)
            sub = result.scalar_one_or_none()

            if sub:
                sub.next_billing_date = datetime.fromtimestamp(
                    invoice["lines"]["data"][0]["period"]["end"], tz=timezone.utc
                ) if invoice.get("lines", {}).get("data") else None
                await db.commit()

        logger.info(f"Invoice paid: {invoice['id']}")
    except (ValueError, TypeError, KeyError, AttributeError, SQLAlchemyError) as e:
        logger.error(f"Error handling invoice paid: {e}")
        await db.rollback()
        raise
