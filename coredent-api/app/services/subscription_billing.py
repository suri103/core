"""
Subscription Billing Service
Handles billing, dunning, and payment retry logic
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID
import stripe as stripe_lib
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.models.subscription import (
    Subscription,
    SubscriptionStatus,
    DunningEvent,
    DunningAction,
    SubscriptionInterval,
)
from app.core.config_simple import settings
from app.core.email import email_service

logger = logging.getLogger(__name__)


class SubscriptionBillingService:
    """Service for subscription billing and dunning operations"""

    @staticmethod
    async def send_dunning_email(
        user_email: str,
        subscription_id: str,
        attempt: int,
        error: str,
    ) -> bool:
        """Send dunning notification email"""
        try:
            await email_service.send_email(
                to=user_email,
                subject=f"Payment Failed - Subscription {subscription_id[:8]} (Attempt {attempt})",
                html_content=f"""
                <html><body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #dc3545;">Payment Issue</h2>
                    <p>We were unable to process your subscription payment.</p>
                    <p><strong>Attempt:</strong> {attempt}</p>
                    <p><strong>Error:</strong> {error}</p>
                    <p>We will automatically retry on the following schedule:</p>
                    <ul>
                        <li>Day 1: Immediate retry</li>
                        <li>Day 3: Second retry</li>
                        <li>Day 7: Third retry</li>
                        <li>Day 14: Final attempt</li>
                    </ul>
                    <p>If all attempts fail, your subscription will be paused.</p>
                    <p><a href="{settings.FRONTEND_URL}/subscriptions/billing" 
                        style="background: #007bff; color: white; padding: 12px 24px; 
                        text-decoration: none; border-radius: 4px;">Update Payment Method</a></p>
                </body></html>
                """,
                text_content=f"Payment failed for subscription {subscription_id[:8]}. Attempt {attempt}. We will retry automatically.",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send dunning email: {e}")
            return False

    @staticmethod
    async def send_trial_expiring_email(
        user_email: str,
        subscription_id: str,
        trial_end: datetime,
    ) -> bool:
        """Send trial expiration warning"""
        try:
            await email_service.send_email(
                to=user_email,
                subject="Trial Ending Soon - CoreDent",
                html_content=f"""
                <html><body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #17a2b8;">Trial Ending Soon</h2>
                    <p>Your CoreDent trial ends on <strong>{trial_end.strftime('%B %d, %Y')}</strong>.</p>
                    <p>Subscribe now to continue enjoying all features:</p>
                    <p><a href="{settings.FRONTEND_URL}/subscriptions/plans" 
                        style="background: #28a745; color: white; padding: 12px 24px; 
                        text-decoration: none; border-radius: 4px;">Choose a Plan</a></p>
                </body></html>
                """,
                text_content=f"Your CoreDent trial ends on {trial_end.strftime('%B %d, %Y')}. Choose a plan to continue.",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send trial expiry email: {e}")
            return False

    @staticmethod
    async def send_payment_receipt(
        user_email: str,
        invoice_number: str,
        amount: Decimal,
        subscription_id: str,
    ) -> bool:
        """Send payment receipt email"""
        try:
            await email_service.send_email(
                to=user_email,
                subject=f"Payment Receipt - Invoice {invoice_number}",
                html_content=f"""
                <html><body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #28a745;">Payment Receipt</h2>
                    <p>Thank you for your payment!</p>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Invoice:</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{invoice_number}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Amount:</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${amount:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Subscription:</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{subscription_id[:8]}</td>
                        </tr>
                    </table>
                    <p style="margin-top: 20px;">Download your full invoice from your account.</p>
                </body></html>
                """,
                text_content=f"Payment receipt: Invoice {invoice_number}, Amount ${amount:.2f}",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send receipt email: {e}")
            return False

    @staticmethod
    async def process_dunning(
        db: AsyncSession,
        background_tasks: Any,
        practice_id: Optional[UUID] = None,
    ) -> Dict[str, int]:
        """
        Run dunning process for past-due subscriptions.
        Automated retry system: Day 0, 3, 7, 14 with email notifications.
        """
        now = datetime.now(timezone.utc)

        # Find subscriptions that need dunning. A NULL next_retry_at means
        # "due now": the stripe.py status-sync path marks subscriptions
        # PAST_DUE without scheduling a retry instant, and `NULL <= now`
        # would silently exclude those rows from the sweep forever.
        query = select(Subscription).where(
            Subscription.status == SubscriptionStatus.PAST_DUE,
            Subscription.dunning_retry_count < Subscription.dunning_max_retries,
            or_(
                Subscription.next_retry_at.is_(None),
                Subscription.next_retry_at <= now,
            ),
        )
        if practice_id:
            query = query.where(Subscription.practice_id == practice_id)

        from app.core.database import row_locks_supported
        if row_locks_supported():
            query = query.with_for_update(skip_locked=True)

        result = await db.execute(query)
        subs = result.scalars().all()

        processed_count = 0
        failed_count = 0

        # M20 FIX: the transaction (and with it every ``FOR UPDATE`` row lock
        # taken above) is held open across the WHOLE read-check-write
        # sequence. The previous per-row ``db.commit()`` released all locks at
        # the first commit, so a stripe status-sync webhook could flip a later
        # row's status mid-batch and the stale ORM state (expire_on_commit is
        # False) would overwrite it. Each row now runs inside a savepoint:
        # a failure rolls back only that row's changes, and the single final
        # commit makes the whole sweep atomic against concurrent writers.
        for sub in subs:
            try:
                async with db.begin_nested():
                    # Create dunning event
                    dunning_event = DunningEvent(
                        subscription_id=sub.id,
                        attempt_number=(sub.dunning_retry_count or 0) + 1,
                        action=DunningAction.RETRY_PAYMENT,
                        scheduled_at=now,
                    )
                    db.add(dunning_event)

                    # Attempt payment retry via Stripe (sync SDK — offload)
                    if settings.STRIPE_API_KEY and sub.stripe_subscription_id:
                        try:
                            import asyncio
                            invoices = await asyncio.to_thread(
                                stripe_lib.Invoice.list,
                                subscription=sub.stripe_subscription_id,
                                status="open",
                                limit=1
                            )

                            if invoices and invoices.data:
                                invoice = invoices.data[0]
                                paid_inv = await asyncio.to_thread(stripe_lib.Invoice.pay, invoice.id)
                                if paid_inv and getattr(paid_inv, "status", None) == "paid":
                                    dunning_event.result = "success"
                                    dunning_event.executed_at = now
                                    sub.status = SubscriptionStatus.ACTIVE
                                    sub.dunning_retry_count = 0
                                    sub.last_payment_error = None
                                    processed_count += 1
                                    continue
                                else:
                                    raise stripe_lib.error.CardError(
                                        message="Invoice payment attempt did not succeed",
                                        param="invoice",
                                        code="payment_failed",
                                    )
                            else:
                                raise stripe_lib.error.CardError(
                                    message="No open invoice found for subscription",
                                    param="subscription",
                                    code="invoice_not_found",
                                )

                        except stripe_lib.error.StripeError as e:
                            error_msg = str(e)
                    else:
                        error_msg = "Stripe is not configured or subscription lacks stripe_subscription_id"

                    dunning_event.result = "failed"
                    dunning_event.error_message = error_msg
                    dunning_event.executed_at = now
                    sub.dunning_retry_count = (sub.dunning_retry_count or 0) + 1
                    sub.last_payment_error = error_msg

                    # Schedule next retry. dunning_retry_count was just
                    # incremented (1-based attempt that failed), so the
                    # next delay is retry_days[count] — the previous
                    # `count - 1` was off-by-one (retry #1 rescheduled
                    # for 0 days instead of 3).
                    retry_days = [0, 3, 7, 14]
                    retry_idx = sub.dunning_retry_count

                    if retry_idx < len(retry_days):
                        sub.next_retry_at = now + timedelta(days=retry_days[retry_idx])
                        dunning_event.action = DunningAction.SEND_EMAIL

                        # Send dunning email in background.
                        # NOTE: Subscription has no `user` relationship —
                        # resolve a practice owner/admin email instead.
                        owner_email = await SubscriptionBillingService._get_practice_billing_email(
                            db, sub.practice_id
                        )
                        if owner_email and background_tasks:
                            background_tasks.add_task(
                                SubscriptionBillingService.send_dunning_email,
                                owner_email,
                                str(sub.id),
                                sub.dunning_retry_count,
                                error_msg
                            )
                    else:
                        sub.status = SubscriptionStatus.UNPAID
                        dunning_event.action = DunningAction.CANCEL_SUBSCRIPTION
                        dunning_event.result = "cancelled"

                    failed_count += 1

            except Exception as e:
                # The savepoint rolls back only this row's changes; the row
                # locks on the remaining subscriptions stay held.
                logger.error(f"Dunning process error for {sub.id}: {e}")
                failed_count += 1

        # Single commit at the end: the FOR UPDATE locks taken above are held
        # until here, so no concurrent writer could have observed (or
        # overwritten) a half-processed batch.
        await db.commit()

        return {
            "processed": processed_count,
            "failed": failed_count,
            "total": len(subs)
        }

    @staticmethod
    async def _get_practice_billing_email(db: AsyncSession, practice_id) -> Optional[str]:
        """Resolve a billing contact email (owner/admin) for a practice."""
        from app.models.user import User, UserRole
        result = await db.execute(
            select(User.email).where(
                User.practice_id == practice_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.OWNER, UserRole.ADMIN]),
            ).order_by(User.created_at).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def calculate_mrr(
        db: AsyncSession,
        practice_id: UUID,
    ) -> Decimal:
        """Calculate Monthly Recurring Revenue"""
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.practice_id == practice_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
            )
        )
        active_subs = result.scalars().all()

        from decimal import ROUND_HALF_UP as _HALF_UP

        # MRR is display-only but keep it cent-exact (was unquantized /12 etc).
        mrr = Decimal(0)
        for sub in active_subs:
            if sub.plan:
                _amt = Decimal(str(sub.plan.amount))
                if sub.plan.interval == SubscriptionInterval.MONTHLY:
                    mrr += _amt
                elif sub.plan.interval == SubscriptionInterval.ANNUAL:
                    mrr += (_amt / 12).quantize(Decimal("0.01"), rounding=_HALF_UP)
                elif sub.plan.interval == SubscriptionInterval.QUARTERLY:
                    mrr += (_amt / 3).quantize(Decimal("0.01"), rounding=_HALF_UP)
                elif sub.plan.interval == SubscriptionInterval.SEMI_ANNUAL:
                    mrr += (_amt / 6).quantize(Decimal("0.01"), rounding=_HALF_UP)
                elif sub.plan.interval == SubscriptionInterval.WEEKLY:
                    mrr += (_amt * Decimal("4.33")).quantize(Decimal("0.01"), rounding=_HALF_UP)

        return mrr.quantize(Decimal("0.01"), rounding=_HALF_UP)

    @staticmethod
    async def calculate_churn_rate(
        db: AsyncSession,
        practice_id: UUID,
    ) -> float:
        """Calculate monthly churn rate"""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Count active subscriptions
        active_result = await db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.practice_id == practice_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
            )
        )
        total_active = active_result.scalar() or 0

        # Count canceled this month
        canceled_result = await db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.practice_id == practice_id,
                Subscription.status == SubscriptionStatus.CANCELED,
                Subscription.canceled_at >= month_start,
            )
        )
        total_canceled = canceled_result.scalar() or 0

        if total_active + total_canceled == 0:
            return 0.0

        return (total_canceled / (total_active + total_canceled)) * 100

    @staticmethod
    async def calculate_average_lifetime(
        db: AsyncSession,
        practice_id: UUID,
    ) -> float:
        """Calculate average subscription lifetime in days"""
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Subscription.created_at).where(
                Subscription.practice_id == practice_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
            )
        )
        created_dates = result.scalars().all()

        if not created_dates:
            return 0.0

        total_days = sum(
            (now - (cd if cd.tzinfo else cd.replace(tzinfo=timezone.utc))).total_seconds() / 86400
            for cd in created_dates
        )
        return total_days / len(created_dates)

    @staticmethod
    async def get_subscription_stats(
        db: AsyncSession,
        practice_id: UUID,
    ) -> Dict[str, Any]:
        """Get comprehensive subscription statistics"""
        # Count by status
        status_counts = {}
        for status_val in SubscriptionStatus:
            result = await db.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.practice_id == practice_id,
                    Subscription.status == status_val,
                )
            )
            status_counts[status_val.name.lower()] = result.scalar() or 0

        canceled_all_time = status_counts.get("canceled", 0)
        canceled_this_month = 0
        if canceled_all_time > 0:
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            res = await db.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.practice_id == practice_id,
                    Subscription.status == SubscriptionStatus.CANCELED,
                    Subscription.canceled_at >= month_start,
                )
            )
            canceled_this_month = res.scalar() or 0

        # Calculate metrics
        mrr = await SubscriptionBillingService.calculate_mrr(db, practice_id)
        churn_rate = await SubscriptionBillingService.calculate_churn_rate(db, practice_id)
        avg_lifetime = await SubscriptionBillingService.calculate_average_lifetime(db, practice_id)

        from decimal import Decimal
        return {
            "total_active": status_counts.get("active", 0),
            "total_trials": status_counts.get("trialing", 0),
            "total_past_due": status_counts.get("past_due", 0),
            "total_canceled_this_month": canceled_this_month,
            "mrr": Decimal(str(mrr)) if mrr is not None else Decimal("0.00"),
            "mrr_growth_percent": 0.0,
            "churn_rate": round(churn_rate, 2),
            "trial_conversion_rate": 0.0,
            "average_lifetime_days": round(avg_lifetime, 1),
        }
