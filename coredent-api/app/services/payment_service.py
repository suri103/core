"""
Payment Service
Core business logic for payment operations

Transaction discipline: mutation methods here only ``flush`` — callers own
the ``commit``. This lets webhook handlers record a payment AND transition
the invoice in one atomic transaction (a crash can no longer leave a PAID
invoice with no payment record, or vice versa).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.billing import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

_CENT = Decimal("0.01")

# Valid payment status transitions. REFUNDED is terminal; COMPLETED->FAILED
# (retroactive failure) must go through a refund, not a status rewrite.
# PARTIALLY_REFUNDED (2026-09) sits between COMPLETED and REFUNDED on the
# manual-refund path (POST /billing/payments/{id}/refund).
_PAYMENT_TRANSITIONS: Dict[PaymentStatus, set] = {
    PaymentStatus.PENDING: {PaymentStatus.COMPLETED, PaymentStatus.FAILED},
    PaymentStatus.FAILED: {PaymentStatus.COMPLETED},
    PaymentStatus.COMPLETED: {PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED},
    PaymentStatus.PARTIALLY_REFUNDED: {PaymentStatus.REFUNDED},
    PaymentStatus.REFUNDED: set(),
}

# Invoice statuses a new payment may be applied to.
_PAYABLE_INVOICE_STATUSES = (
    InvoiceStatus.PENDING,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.OVERDUE,
)


def _dec(value: Any) -> Decimal:
    """Coerce Numeric/str/float money values to Decimal exactly once."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _lock_invoice(db: AsyncSession, stmt):
    """Apply FOR UPDATE on Postgres only (SQLite: dev-only, no row locks)."""
    from app.core.database import row_locks_supported
    if row_locks_supported():
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


class PaymentService:
    """Service for payment operations"""

    @staticmethod
    async def get_invoice(
        db: AsyncSession,
        invoice_id: UUID,
        practice_id: UUID,
    ) -> Optional[Invoice]:
        """Get an invoice only within the caller's tenant."""
        result = await db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.practice_id == practice_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_payment(
        db: AsyncSession,
        transaction_id: str,
        practice_id: UUID,
        *,
        for_update: bool = False,
    ) -> Optional[Payment]:
        """Get a payment by (practice_id, transaction_id).

        Scoped to the composite unique (H3 FIX) — the old Join(Invoice) form
        is equivalent but indirect now that Payment carries practice_id.
        for_update=True takes a row lock for refund read-modify-write (H2).
        """
        from app.core.database import row_locks_supported

        stmt = select(Payment).where(
            Payment.transaction_id == transaction_id,
            Payment.practice_id == practice_id,
        )
        if for_update and row_locks_supported():
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_payment_record(
        db: AsyncSession,
        invoice_id: UUID,
        patient_id: UUID,
        practice_id: UUID,
        amount,
        payment_method,
        transaction_id: str,
        status: PaymentStatus,
        notes: str = "",
    ) -> Payment:
        """Create a tenant-validated payment record.

        The HTTP endpoint is not the service boundary: webhook, worker, and
        future CLI callers must also prove the invoice and patient belong to
        the supplied practice before a ledger row is written.
        """
        invoice = await _lock_invoice(
            db,
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.practice_id == practice_id,
            ),
        )
        if invoice is None:
            raise ValueError("Invoice not found")
        if invoice.patient_id != patient_id:
            raise ValueError("Payment patient does not match invoice patient")

        try:
            payment_status = (
                status if isinstance(status, PaymentStatus) else PaymentStatus(status)
            )
            method = (
                payment_method
                if isinstance(payment_method, PaymentMethod)
                else PaymentMethod(payment_method)
            )
        except ValueError as exc:
            raise ValueError("Invalid payment status or method") from exc

        if payment_status == PaymentStatus.REFUNDED:
            raise ValueError("Refunded payments must be created through the refund flow")
        if invoice.status not in _PAYABLE_INVOICE_STATUSES:
            raise ValueError(f"Invoice is not payable (status: {invoice.status})")

        amount_decimal = _dec(amount).quantize(_CENT)
        if amount_decimal <= 0:
            raise ValueError("Payment amount must be greater than zero")
        if payment_status == PaymentStatus.COMPLETED:
            balance_due = _dec(invoice.balance_due).quantize(_CENT)
            if amount_decimal > balance_due:
                raise ValueError("Payment amount exceeds invoice balance")

        if transaction_id:
            existing_result = await db.execute(
                select(Payment)
                .join(Invoice)
                .where(
                    Payment.transaction_id == transaction_id,
                    Invoice.practice_id == practice_id,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                same_payment = (
                    existing.invoice_id == invoice_id
                    and existing.patient_id == patient_id
                    and _dec(existing.amount).quantize(_CENT) == amount_decimal
                    and existing.payment_method == method
                    and existing.status == payment_status
                )
                if same_payment:
                    return existing
                raise ValueError("Transaction ID is already used by another payment")

        payment = Payment(
            invoice_id=invoice_id,
            patient_id=patient_id,
            practice_id=practice_id,
            amount=amount_decimal,
            payment_method=method,
            transaction_id=transaction_id,
            status=payment_status,
            notes=notes,
        )
        db.add(payment)
        await db.flush()
        logger.info(
            "Recorded payment %s for invoice %s (%s)",
            payment.id,
            invoice_id,
            payment_status.value,
        )
        return payment

    @staticmethod
    async def completed_total(
        db: AsyncSession,
        invoice_id: UUID,
        practice_id: UUID,
    ) -> Decimal:
        """Return effective collected money for a tenant-owned invoice."""
        result = await db.execute(
            select(
                func.sum(Payment.amount - func.coalesce(Payment.refunded_amount, 0))
            )
            .join(Invoice)
            .where(
                Payment.invoice_id == invoice_id,
                Invoice.id == invoice_id,
                Invoice.practice_id == practice_id,
                Payment.status.in_(
                    (
                        PaymentStatus.COMPLETED,
                        PaymentStatus.REFUNDED,
                        PaymentStatus.PARTIALLY_REFUNDED,
                    )
                ),
            )
        )
        return _dec(result.scalar() or 0)

    @staticmethod
    async def refresh_invoice_status(
        db: AsyncSession,
        invoice_id: UUID,
        practice_id: UUID,
    ) -> Optional[Invoice]:
        """Recompute a tenant-owned invoice from its payment ledger."""
        stmt = select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.practice_id == practice_id,
        )
        invoice = await _lock_invoice(db, stmt)
        if not invoice or invoice.status in (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED):
            return invoice

        paid = await PaymentService.completed_total(db, invoice_id, practice_id)
        total = _dec(invoice.total)
        if paid > total:
            raise ValueError("Completed payments exceed invoice total")
        if paid >= total:
            invoice.status = InvoiceStatus.PAID
        elif paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        elif invoice.status != InvoiceStatus.OVERDUE:
            invoice.status = InvoiceStatus.PENDING
        await db.flush()
        return invoice

    @staticmethod
    async def apply_payment_transition(
        db: AsyncSession,
        invoice_id: UUID,
        practice_id: UUID,
    ) -> Invoice:
        """
        Recompute the invoice status from its COMPLETED payments.

        Amount-aware replacement for the old unconditional ``PAID`` flip:
        a partial payment moves the invoice to PARTIALLY_PAID, only a
        payment that clears the balance marks it PAID. Flushes; the caller
        commits, so the payment record and this transition are atomic.
        """
        stmt = select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.practice_id == practice_id,
        )
        invoice = await _lock_invoice(db, stmt)

        if not invoice:
            raise ValueError("Invoice not found")

        if invoice.status not in _PAYABLE_INVOICE_STATUSES:
            # CANCELLED/DRAFT invoices must not receive payment-driven
            # status flips; the caller should have rejected the payment.
            raise ValueError(f"Invoice is not payable (status: {invoice.status})")

        paid = await PaymentService.completed_total(db, invoice_id, practice_id)
        total = _dec(invoice.total)
        if paid > total:
            raise ValueError("Completed payments exceed invoice total")

        if paid >= total:
            invoice.status = InvoiceStatus.PAID
        elif paid > 0:
            # PENDING and OVERDUE both move to PARTIALLY_PAID on a partial
            # payment (OVERDUE/PARTIALLY_PAID were previously stuck).
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        await db.flush()
        return invoice

    @staticmethod
    async def mark_invoice_paid(
        db: AsyncSession,
        invoice_id: UUID,
        practice_id: UUID,
    ) -> Optional[Invoice]:
        """Compatibility wrapper for an amount-aware ledger transition.

        This method deliberately does not assign ``PAID`` directly. The
        status is derived from completed, refunded-aware ledger rows.
        """
        return await PaymentService.apply_payment_transition(
            db, invoice_id, practice_id
        )

    @staticmethod
    async def update_payment_status(
        db: AsyncSession,
        payment_id: UUID,
        status: PaymentStatus,
        practice_id: UUID,
    ) -> Optional[Payment]:
        """Update a payment only when its parent invoice is tenant-owned."""
        query = (
            select(Payment)
            .join(Invoice)
            .where(
                Payment.id == payment_id,
                Invoice.practice_id == practice_id,
            )
        )
        from app.core.database import row_locks_supported
        if row_locks_supported():
            query = query.with_for_update()
        result = await db.execute(query)
        payment = result.scalar_one_or_none()

        if not payment:
            return None

        try:
            requested_status = (
                status
                if isinstance(status, PaymentStatus)
                else PaymentStatus(status)
            )
            current_status = (
                payment.status
                if isinstance(payment.status, PaymentStatus)
                else PaymentStatus(payment.status)
            )
        except ValueError as exc:
            raise ValueError("Invalid payment status") from exc

        if current_status == requested_status:
            return payment

        allowed = _PAYMENT_TRANSITIONS.get(current_status, set())
        if requested_status not in allowed:
            raise ValueError(
                f"Illegal payment status transition: "
                f"{current_status} -> {requested_status}"
            )

        payment.status = requested_status
        await db.flush()

        # Recompute under the same tenant scope. This rejects an overpayment
        # instead of silently marking an invoice paid.
        await PaymentService.refresh_invoice_status(
            db, payment.invoice_id, practice_id
        )
        await db.commit()
        await db.refresh(payment)
        logger.info("Updated payment %s status to %s", payment_id, requested_status)
        return payment

    @staticmethod
    async def list_payments(
        db: AsyncSession,
        practice_id: UUID,
        status: Optional[PaymentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Payment], int]:
        """List payments with filtering and pagination"""
        query = (
            select(Payment)
            .join(Invoice)
            .where(Invoice.practice_id == practice_id)
            .order_by(Payment.created_at.desc())
        )

        if status:
            query = query.where(Payment.status == status)

        if start_date:
            query = query.where(Payment.created_at >= start_date)

        if end_date:
            query = query.where(Payment.created_at <= end_date)

        # Get total count — must apply the SAME filters as the data query,
        # otherwise pagination totals are wrong whenever filters are used.
        count_query = (
            select(func.count(Payment.id))
            .join(Invoice)
            .where(Invoice.practice_id == practice_id)
        )
        if status:
            count_query = count_query.where(Payment.status == status)
        if start_date:
            count_query = count_query.where(Payment.created_at >= start_date)
        if end_date:
            count_query = count_query.where(Payment.created_at <= end_date)
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        payments = result.scalars().all()

        return payments, total

    @staticmethod
    async def get_payment_stats(
        db: AsyncSession,
        practice_id: UUID,
    ) -> Dict[str, Any]:
        """
        Payment statistics for the practice.

        M10 FIX: revenue is derived from COMPLETED payments by payment date
        (``Payment.created_at``), not from ``Invoice.updated_at`` — any
        touch (note edit, status change) used to re-book an old invoice
        into today's revenue. ``today_transactions`` counts payments, not
        invoices.
        """
        # TZ FIX: bucket by practice-local day like reports.py/appointments.py
        # (UTC midnight shifted IST revenue a day).
        from app.core.business_time import day_bounds_utc, get_practice_timezone

        from app.core.business_time import business_date as _biz_date

        practice_tz = await get_practice_timezone(db, practice_id)
        now = datetime.now(timezone.utc)
        today_start, _ = day_bounds_utc(practice_tz, _biz_date(practice_tz, now))
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        def _completed_since(start: datetime, end: Optional[datetime] = None):
            q = (
                select(func.sum(Payment.amount), func.count(Payment.id))
                .join(Invoice)
                .where(
                    Invoice.practice_id == practice_id,
                    Payment.status == PaymentStatus.COMPLETED,
                    Payment.created_at >= start,
                )
            )
            if end is not None:
                q = q.where(Payment.created_at < end)
            return q

        async def _sum_count(q):
            # Float FIX: keep cent-exact Decimals (float(total) lost cents vs
            # _dec().quantize(_CENT) elsewhere). Response serializes Decimals.
            from decimal import Decimal as _D

            result = await db.execute(q)
            total, count = result.first()
            return (_D(str(total)) if total is not None else _D("0")), int(count or 0)

        today_revenue, today_transactions = await _sum_count(_completed_since(today_start))
        month_revenue, _ = await _sum_count(_completed_since(month_start))
        last_month_revenue, _ = await _sum_count(_completed_since(last_month_start, month_start))

        # Calculate growth percentage
        if last_month_revenue > 0:
            month_growth = round(((month_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
        else:
            month_growth = 0 if month_revenue == 0 else 100

        # Outstanding balances across unpaid, non-draft invoices.
        outstanding_result = await db.execute(
            select(Invoice.total, Invoice.id).where(
                Invoice.practice_id == practice_id,
                Invoice.status.in_(_PAYABLE_INVOICE_STATUSES),
            )
        )
        from decimal import Decimal as _D2

        pending_amount = _D2("0")
        pending_count = 0
        for total, invoice_id in outstanding_result.all():
            paid = await PaymentService.completed_total(db, invoice_id, practice_id)
            balance = _dec(total) - paid
            if balance > 0:
                pending_amount += balance
                pending_count += 1

        return {
            "today_revenue": today_revenue,
            "today_transactions": today_transactions,
            "month_revenue": month_revenue,
            "month_growth": month_growth,
            "pending_amount": pending_amount,
            "pending_count": pending_count,
        }
