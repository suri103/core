"""
Payment Gateway Endpoints (Razorpay)

Order creation, client-side payment verification, and the refund webhook.
Stripe card/subscription processing lives in ``stripe.py``; the shared
processor logic lives in ``app.services.payment_processing``.

The Razorpay flow is client-initiated: the frontend creates an order here,
opens Razorpay Checkout with the returned ``key_id``/``order_id``, then posts
the checkout callback signature to ``/razorpay/verify`` which records the
payment against the invoice. Refunds issued from the Razorpay dashboard
never pass through this API, so ``/razorpay/webhook`` reconciles them into
the local ledger — mirroring the Stripe ``charge.refunded`` handling.
"""

import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.webhook_security import WebhookVerificationError, verify_razorpay_signature
from app.models.billing import Invoice, Payment, PaymentStatus
from app.models.processor_event import ProcessorEventStatus, ProcessorWebhookEvent
from app.models.user import User, UserRole
from app.services.payment_processing import RazorpayPaymentProcessor
from app.services.payment_service import PaymentService
from app.services.processor_events import record_event

logger = logging.getLogger(__name__)

router = APIRouter()

# Same roles that may post manual payments in billing.py.
_PAYMENT_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.FRONT_DESK, UserRole.ACCOUNTANT)

_CENT = Decimal("0.01")


class RazorpayOrderRequest(BaseModel):
    invoice_id: UUID
    amount: Optional[Decimal] = Field(
        None, description="Partial payment amount; defaults to the invoice balance"
    )
    currency: str = "INR"
    receipt: Optional[str] = None


class RazorpayVerifyRequest(BaseModel):
    invoice_id: UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _processor_error(exc: ValueError) -> HTTPException:
    """Map processor ValueErrors onto meaningful HTTP statuses."""
    message = str(exc)
    if "credentials not configured" in message:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay is not configured for this deployment",
        )
    if message == "Invoice not found":
        return HTTPException(status_code=404, detail="Invoice not found")
    return HTTPException(status_code=400, detail=message)


@router.post("/razorpay/order")
async def create_razorpay_order(
    data: RazorpayOrderRequest,
    request: Request,
    current_user: User = Depends(require_role(*_PAYMENT_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Create a Razorpay order for an invoice so the frontend can open Checkout."""
    try:
        order = await RazorpayPaymentProcessor.create_order(
            db=db,
            current_user=current_user,
            invoice_id=data.invoice_id,
            amount=data.amount,
            currency=data.currency,
            receipt=data.receipt,
        )
    except ValueError as exc:
        raise _processor_error(exc) from exc

    await log_audit_event(
        db, current_user, "razorpay_order_created", "invoice",
        data.invoice_id, request,
        changes={"order_id": order["order_id"], "amount_minor": order["amount"]},
    )
    await db.commit()
    return order


@router.post("/razorpay/verify")
async def verify_razorpay_payment(
    data: RazorpayVerifyRequest,
    request: Request,
    current_user: User = Depends(require_role(*_PAYMENT_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Verify the Razorpay Checkout signature and record the payment.

    The processor validates the HMAC signature, confirms the payment status
    with Razorpay, enforces the invoice balance, and records the payment
    idempotently (unique transaction_id).
    """
    try:
        result = await RazorpayPaymentProcessor.verify_payment(
            db=db,
            invoice_id=data.invoice_id,
            razorpay_order_id=data.razorpay_order_id,
            razorpay_payment_id=data.razorpay_payment_id,
            razorpay_signature=data.razorpay_signature,
            practice_id=current_user.practice_id,
        )
    except ValueError as exc:
        raise _processor_error(exc) from exc

    await log_audit_event(
        db, current_user, "razorpay_payment_verified", "invoice",
        data.invoice_id, request,
        changes={
            "razorpay_payment_id": data.razorpay_payment_id,
            "duplicate": result.get("duplicate", False),
        },
    )
    await db.commit()
    return {**result, "verified": True}


@router.post("/razorpay/webhook", include_in_schema=False)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reconcile processor-initiated refunds into the local ledger.

    Signature-verified (fail-closed without RAZORPAY_WEBHOOK_SECRET) and
    idempotent per Razorpay refund id via the durable
    ``processor_webhook_events`` ledger, mirroring the Stripe webhook's
    "never answer 200 for money we did not record" invariant.
    """
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature") or ""

    try:
        verify_razorpay_signature(payload, received_signature=signature)
    except WebhookVerificationError as exc:
        logger.warning("Razorpay webhook rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Webhook body is not valid JSON") from exc

    event_type = event.get("event") or "unknown"
    refund_entity: Dict[str, Any] = (
        event.get("payload", {}).get("refund", {}).get("entity", {}) or {}
    )

    if event_type != "refund.processed":
        await record_event(
            db,
            processor="razorpay",
            event_id=refund_entity.get("id") or event.get("id"),
            event_type=event_type,
            payload=refund_entity or event,
            status=ProcessorEventStatus.IGNORED,
        )
        await db.commit()
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    refund_id = refund_entity.get("id")
    if not refund_id:
        logger.error("Razorpay refund.processed event without a refund id")
        raise HTTPException(status_code=400, detail="Refund event missing refund id")

    # Idempotency: a redelivered refund must not be applied twice.
    existing_row = (
        await db.execute(
            select(ProcessorWebhookEvent).where(
                ProcessorWebhookEvent.event_id == refund_id
            )
        )
    ).scalar_one_or_none()
    if existing_row is not None and existing_row.status == ProcessorEventStatus.PROCESSED:
        return JSONResponse(status_code=200, content={"ok": True, "duplicate": True})

    payment_txn_id = refund_entity.get("payment_id")
    # H3 FIX: transaction_id is unique per (practice_id, transaction_id), and
    # this webhook is signature-only (no tenant context). Never guess across
    # tenants: 0 rows -> quarantine, >1 rows -> quarantine ambiguous for an
    # operator, exactly 1 -> apply under a row lock (H2 FIX).
    from app.core.database import row_locks_supported as _locks_ok

    _stmt = select(Payment).where(Payment.transaction_id == payment_txn_id)
    if _locks_ok():
        _stmt = _stmt.with_for_update()
    _matches = (await db.execute(_stmt)).scalars().all()
    if len(_matches) > 1:
        logger.critical(
            "UNRECONCILED REFUND: Razorpay refund %s matches %d ledger rows "
            "for transaction %s across practices; refusing to guess.",
            refund_id,
            len(_matches),
            payment_txn_id,
        )
        await record_event(
            db,
            processor="razorpay",
            event_id=refund_id,
            event_type=event_type,
            payload=refund_entity,
            status=ProcessorEventStatus.UNRECONCILED,
            error_message="transaction_id ambiguous across practices; needs operator",
        )
        await db.commit()
        return JSONResponse(status_code=200, content={"ok": True})
    payment = _matches[0] if _matches else None

    if payment is None:
        # Money moved externally but we have no ledger row: quarantine for
        # an operator instead of acknowledging silently.
        logger.critical(
            "UNRECONCILED REFUND: Razorpay refund %s for payment %s has no "
            "local ledger row. Quarantined for reconciliation.",
            refund_id,
            payment_txn_id,
        )
        await record_event(
            db,
            processor="razorpay",
            event_id=refund_id,
            event_type=event_type,
            payload=refund_entity,
            status=ProcessorEventStatus.UNRECONCILED,
            error_message="no local Payment for refunded Razorpay payment",
        )
        await db.commit()
        return JSONResponse(status_code=200, content={"ok": True})

    refund_amount = (Decimal(refund_entity.get("amount") or 0) / Decimal(100)).quantize(_CENT)
    already_refunded = Decimal(str(payment.refunded_amount or 0))
    total = Decimal(str(payment.amount))
    new_refunded = already_refunded + refund_amount

    if refund_amount <= 0 or new_refunded > total:
        # Never silently rewrite the ledger; quarantine the anomaly.
        logger.critical(
            "UNRECONCILED REFUND: Razorpay refund %s amount %s is invalid "
            "against payment %s (already refunded %s of %s).",
            refund_id,
            refund_amount,
            payment_txn_id,
            already_refunded,
            total,
        )
        await record_event(
            db,
            processor="razorpay",
            event_id=refund_id,
            event_type=event_type,
            payload=refund_entity,
            status=ProcessorEventStatus.UNRECONCILED,
            error_message=(
                f"refund amount {refund_amount} invalid against already-refunded "
                f"{already_refunded} of {total}"
            ),
        )
        await db.commit()
        return JSONResponse(status_code=200, content={"ok": True})

    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == payment.invoice_id))
    ).scalar_one_or_none()

    # Move event insertion before money mutation and flush to catch concurrent delivery races (M2)
    try:
        await record_event(
            db,
            processor="razorpay",
            event_id=refund_id,
            event_type=event_type,
            payload=refund_entity,
            status=ProcessorEventStatus.PROCESSED,
            practice_id=invoice.practice_id if invoice is not None else payment.practice_id,
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("Concurrent Razorpay refund webhook race won by peer: %s", refund_id)
        return JSONResponse(status_code=200, content={"ok": True, "duplicate": True})

    payment.refunded_amount = new_refunded
    if new_refunded >= total:
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED

    if invoice is not None:
        await PaymentService.refresh_invoice_status(db, invoice.id, invoice.practice_id)

    await db.commit()
    logger.info("Razorpay refund recorded for payment %s: %s", payment.id, refund_amount)
    return JSONResponse(status_code=200, content={"ok": True})


@router.get("/transactions")
async def list_payment_transactions(
    request: Request,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_role(*_PAYMENT_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List tenant-scoped payment ledger rows for the Payments dashboard."""
    from sqlalchemy.orm import joinedload
    from app.models.patient import Patient

    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    stmt = (
        select(Payment)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .outerjoin(Patient, Patient.id == Payment.patient_id)
        .where(Invoice.practice_id == current_user.practice_id)
        .options(joinedload(Payment.patient), joinedload(Payment.invoice))
        .order_by(Payment.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    q = (search or "").strip().lower()
    transactions = []
    for p in rows:
        patient_name = (
            f"{p.patient.first_name or ''} {p.patient.last_name or ''}".strip()
            if p.patient is not None
            else "Patient"
        )
        method_val = getattr(p.payment_method, "value", str(p.payment_method or "card"))
        status_val = getattr(p.status, "value", str(p.status or "completed"))
        if q:
            haystack = f"{patient_name} {p.transaction_id or ''} {method_val}".lower()
            if q not in haystack:
                continue
        transactions.append(
            {
                "id": str(p.id),
                "patient_id": str(p.patient_id) if p.patient_id else None,
                "patient_name": patient_name,
                "invoice_id": str(p.invoice_id) if p.invoice_id else None,
                "amount": float(Decimal(str(p.amount or 0)) - Decimal(str(p.refunded_amount or 0))),
                "type": "Refund" if status_val == "refunded" else "Payment",
                "payment_method": method_val,
                "status": status_val,
                "date": p.created_at.isoformat() if p.created_at else None,
                "transaction_id": p.transaction_id,
            }
        )
    await log_audit_event(
        db, current_user, "list_payment_transactions", "payment", None, request
    )
    await db.commit()
    return {"transactions": transactions, "count": len(transactions)}


@router.get("/plans")
async def list_recurring_payment_plans(
    request: Request,
    current_user: User = Depends(require_role(*_PAYMENT_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List tenant-scoped installment payment plans for the Payments dashboard."""
    from sqlalchemy.orm import joinedload, selectinload
    from app.models.billing import PaymentPlan

    stmt = (
        select(PaymentPlan)
        .where(PaymentPlan.practice_id == current_user.practice_id)
        .options(joinedload(PaymentPlan.patient), selectinload(PaymentPlan.installments))
        .order_by(PaymentPlan.created_at.desc())
        .limit(100)
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    plans = []
    for plan in rows:
        patient_name = (
            f"{plan.patient.first_name or ''} {plan.patient.last_name or ''}".strip()
            if getattr(plan, "patient", None) is not None
            else "Patient"
        )
        unpaid_installments = sorted(
            [i for i in (plan.installments or []) if getattr(i, "status", "") != "paid"],
            key=lambda i: i.due_date,
        )
        next_inst = unpaid_installments[0] if unpaid_installments else None
        monthly_amount = (
            float(next_inst.amount)
            if next_inst is not None
            else (
                float(plan.installments[0].amount)
                if plan.installments
                else float(plan.total_amount or 0)
            )
        )
        status_val = getattr(plan.status, "value", str(plan.status or "active"))
        plans.append(
            {
                "id": str(plan.id),
                "patient_id": str(plan.patient_id),
                "patient_name": patient_name,
                "name": plan.notes or "Installment Plan",
                "monthly_amount": monthly_amount,
                "total_amount": float(plan.total_amount or 0),
                "frequency": "Monthly",
                "next_payment_date": next_inst.due_date.isoformat() if next_inst and next_inst.due_date else (plan.start_date.isoformat() if plan.start_date else ""),
                "status": status_val,
            }
        )
    return {"plans": plans, "count": len(plans)}


@router.get("/terminals")
async def list_payment_terminals(
    current_user: User = Depends(require_role(*_PAYMENT_ROLES)),
):
    """Return configured POS terminals for the practice (empty until hardware terminal pairing is configured)."""
    return {"terminals": [], "count": 0}
