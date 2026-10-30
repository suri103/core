"""
Billing Endpoints
CRUD operations for invoices and payments

SECURITY HISTORY
----------------
- 2026-02: Replaced the read-then-write invoice-number generation (which
  was racy under concurrent requests and would cause a 500 on the
  ``unique=True`` constraint) with a Postgres advisory lock so two
  concurrent requests serialize.
- 2026-02: Wrapped the payment-creation + invoice-status transition in
  a ``SELECT ... FOR UPDATE`` on the invoice row so two concurrent
  payments for the same invoice cannot both observe ``balance_due > 0``
  and over-pay.
"""

import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

import stripe as stripe_lib
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, text, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.business_time import (
    DateRangeError,
    business_date,
    day_bounds_utc,
    get_practice_timezone,
    resolve_date_range,
)
from app.core.config_simple import settings
from app.core.database import get_db, row_locks_supported
from app.models.billing import (
    Invoice, Payment, InvoiceStatus, PaymentStatus, PaymentMethod,
    PaymentPlan, PaymentPlanInstallment, PaymentPlanStatus,
)
from app.models.patient import Patient
from app.models.payment import PaymentTransaction
from app.models.user import User, UserRole
from app.services.payment_processing import RazorpayPaymentProcessor, _to_cents
from app.services.invoice_status import (
    CREATABLE_STATUSES,
    derive_invoice_status,
    validate_client_status_change,
)
from app.schemas.billing import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    PaymentCreate,
    PaymentResponse,
    PaymentListResponse,
    BillingSummary,
    PaymentPlanCreate,
    PaymentPlanInstallmentPay,
    PaymentPlanResponse,
    PaymentPlanListResponse,
    RefundCreate,
    RefundResponse,
)

logger = logging.getLogger(__name__)

# L-4 FIX: single money rounding mode (HALF_UP) matching gateway cents
# (payment_processing._to_cents). All quantize(cent) below uses it so a .005
# edge never differs by 1c between ledger and gateway.
_MONEY_ROUNDING = ROUND_HALF_UP


def _split_gst(tax: Decimal, is_inter_state: str | None) -> tuple[Decimal, Decimal, Decimal]:
    """Split tax into (cgst, sgst, igst) — L-5 FIX.

    The split columns were always 0 while tax carried the whole amount, so
    any report reading splits under-reported. Inter-state (Y) books IGST;
    otherwise CGST/SGST split the tax, with the odd cent on SGST so the
    three always sum to tax.
    """
    cent = Decimal("0.01")
    tax_q = Decimal(str(tax or 0)).quantize(cent, rounding=_MONEY_ROUNDING)
    if (is_inter_state or "N").upper() == "Y":
        return Decimal("0.00"), Decimal("0.00"), tax_q
    cgst = (tax_q / 2).quantize(cent, rounding=_MONEY_ROUNDING)
    sgst = tax_q - cgst
    return cgst, sgst, Decimal("0.00")


# Roles permitted to move money. Front-desk may bill; clinical-only roles may not.
# PRODUCT DECISION (safe default): billing is a front-office function, so
# OWNER, ADMIN and FRONT_DESK are allowed; DENTIST and HYGIENIST are not.
# Previously every one of these routes was `get_current_user` only, meaning any
# authenticated clinical user could raise invoices and record payments against
# a patient ledger. That fails HIPAA §164.308(a)(4) least-privilege and is the
# wrong blast radius for shared front-desk credentials. Deleting an invoice was
# already OWNER/ADMIN-only, so the guards were also mutually inconsistent.
# Widen this tuple if a practice genuinely needs clinicians to bill.
_BILLING_WRITE_ROLES = (
    UserRole.OWNER,
    UserRole.ADMIN,
    UserRole.FRONT_DESK,
    # ACCOUNTANT (2026-09): finance staff get full billing write access —
    # recording payments and issuing refunds is their job. The role has no
    # access to clinical/Patient-profile routes (see routes/config.tsx).
    UserRole.ACCOUNTANT,
)

router = APIRouter()


def _payment_replay_matches(existing: Payment, requested: PaymentCreate) -> bool:
    """Return whether a transaction-id retry is the same logical payment."""
    existing_method = getattr(existing.payment_method, "value", existing.payment_method)
    requested_method = getattr(requested.payment_method, "value", requested.payment_method)
    return (
        existing.invoice_id == requested.invoice_id
        and existing.patient_id == requested.patient_id
        and Decimal(str(existing.amount)).quantize(Decimal("0.01"))
        == Decimal(str(requested.amount)).quantize(Decimal("0.01"))
        and str(existing_method).lower() == str(requested_method).lower()
        and existing.status == requested.status
    )


def _money(value) -> float:
    """Serialize a money aggregate as a clean two-decimal float.

    SQLite round-trips Numeric columns through binary floats, so an exact
    aggregate can surface as e.g. 19.990000000000002; quantizing to cents
    first makes every reported figure a proper currency amount.
    """
    return float(Decimal(str(0 if value is None else value)).quantize(Decimal("0.01")))

#
# Old code computed ``count(*)`` of today's invoices and used that as the
# sequence number.  Under concurrent inserts two requests both saw the
# same count, both tried to insert the same invoice_number, and one of
# them hit a 500 from the unique constraint.  We now take a transaction-
# scoped Postgres advisory lock keyed on the practice + calendar day, so
# only one insert runs at a time per practice.  The lock is released
# when the transaction commits/rolls back.

async def _next_invoice_number(
    db: AsyncSession, practice_id: UUID, prefix: str = "INV"
) -> str:
    """
    Return the next unique invoice number for ``practice_id`` today.

    Uses ``pg_advisory_xact_lock`` on a 64-bit hash of the practice UUID
    XORed with the YYYYMMDD integer so different practices (and different
    days) do not contend.

    M8 FIX: the number is existence-checked, not just ``count(*) + 1`` —
    count-based numbering regresses when a same-day invoice is hard-deleted
    and reissues an in-use number (unique-constraint 500).

    ``prefix`` comes from ``Practice.invoice_prefix``: the setting was
    previously stored and echoed back by the settings API but never consumed
    here, so a practice that configured "ACME" still got "INV-".
    """
    is_postgres = row_locks_supported()
    practice_tz = await get_practice_timezone(db, practice_id)
    today = business_date(practice_tz)
    start_utc, end_utc = day_bounds_utc(practice_tz, today)

    if is_postgres:
        day_key = int(today.strftime("%Y%m%d"))
        # 63-bit unsigned practice-hash XORed with day_key.  Practice UUID
        # truncated to 8 bytes; we then take the first 8 bytes interpreted
        # as a bigint.  This is not cryptographically interesting; we just
        # need a stable, narrow integer for the lock key.
        practice_int = int.from_bytes(
            practice_id.bytes[:8], byteorder="big", signed=False
        ) & 0x7FFFFFFFFFFFFFFF
        lock_key = (practice_int ^ day_key) & 0x7FFFFFFFFFFFFFFF
        # Advisory lock is held until the current transaction ends.
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    day_prefix = today.strftime("%Y%m%d")
    count_q = select(func.count(Invoice.id)).where(
        Invoice.practice_id == practice_id,
        Invoice.created_at >= start_utc,
        Invoice.created_at < end_utc,
    )
    count = (await db.execute(count_q)).scalar() or 0
    seq = count + 1
    # Skip past numbers still in use (gaps from hard deletes).
    while seq < count + 10000:
        candidate = f"{prefix}-{day_prefix}-{seq:04d}"
        exists = await db.execute(
            select(Invoice.id).where(
                Invoice.practice_id == practice_id,
                Invoice.invoice_number == candidate,
            )
        )
        if exists.scalar_one_or_none() is None:
            return candidate
        seq += 1
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate an invoice number",
    )


# ---------------------------------------------------------------------------
# Practice billing preferences
# ---------------------------------------------------------------------------
#
# ``PUT /settings/billing`` persists these and reads them straight back, so the
# UI reported success -- but nothing on the billing path consumed them. An owner
# who set "Tax Rate 8.5%" and then raised an invoice without an explicit rate
# got 0% tax, and a configured invoice prefix was dropped. These helpers make
# the stored preferences the actual default.

_DEFAULT_INVOICE_PREFIX = "INV"
_DEFAULT_PAYMENT_TERMS_DAYS = 30


async def _get_practice_billing_prefs(
    db: AsyncSession, practice_id: UUID
) -> tuple[Decimal, str, int, bool]:
    """Return ``(tax_rate_fraction, invoice_prefix, payment_terms_days, auto_send_invoices)``.

    NOTE on units: ``Practice.tax_rate`` is stored as a *percent* (the settings
    schema bounds it 0..100) while ``Invoice.tax_rate`` is a *fraction* bounded
    0..1, so the stored value is divided by 100 here. Getting this wrong would
    tax at 850% instead of 8.5%.

    The column is JSON and documented as "float or dict for multiple tax
    rates"; only a scalar can be applied as a single invoice-level rate, so a
    dict falls back to zero rather than guessing which component to use.
    """
    from app.models.practice import Practice

    result = await db.execute(select(Practice).where(Practice.id == practice_id))
    practice = result.scalar_one_or_none()
    if practice is None:
        return (
            Decimal("0.0"),
            _DEFAULT_INVOICE_PREFIX,
            _DEFAULT_PAYMENT_TERMS_DAYS,
            False,
        )

    raw_rate = practice.tax_rate
    tax_rate = Decimal("0.0")
    if isinstance(raw_rate, (int, float)) and not isinstance(raw_rate, bool):
        tax_rate = (Decimal(str(raw_rate)) / Decimal("100")).quantize(Decimal("0.0001"))
    elif isinstance(raw_rate, str):
        try:
            tax_rate = (Decimal(raw_rate) / Decimal("100")).quantize(Decimal("0.0001"))
        except (ArithmeticError, ValueError):
            tax_rate = Decimal("0.0")

    # Clamp into the fraction range the invoice schema accepts.
    if tax_rate < 0 or tax_rate > 1:
        tax_rate = Decimal("0.0")

    prefix = (practice.invoice_prefix or _DEFAULT_INVOICE_PREFIX).strip()
    # Keep the generated number shape predictable and index-friendly.
    if not prefix or not prefix.replace("_", "").replace("-", "").isalnum():
        prefix = _DEFAULT_INVOICE_PREFIX

    raw_terms = practice.payment_terms
    terms = _DEFAULT_PAYMENT_TERMS_DAYS
    if isinstance(raw_terms, int) and not isinstance(raw_terms, bool) and raw_terms > 0:
        terms = raw_terms

    auto_send = bool(practice.auto_send_invoices)
    return tax_rate, prefix.upper(), terms, auto_send


# Invoice Endpoints

@router.get("/invoices/", response_model=InvoiceListResponse)
async def list_invoices(
    # Wire contract keeps the ``status`` query param, but the local name is
    # status_filter: a parameter named ``status`` shadows the fastapi
    # ``status`` module inside this function, which made the DateRangeError
    # path below raise AttributeError (500) instead of a clean 422.
    status_filter: Optional[InvoiceStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    """
    List invoices with optional filters and pagination
    """
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        date_range = resolve_date_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    filters = [
        Invoice.practice_id == current_user.practice_id,
        Invoice.created_at >= date_range.start_utc,
        Invoice.created_at < date_range.end_utc,
    ]
    if status_filter:
        filters.append(Invoice.status == status_filter)
    if patient_id:
        filters.append(Invoice.patient_id == patient_id)

    total = (
        await db.execute(select(func.count(Invoice.id)).where(*filters))
    ).scalar_one()
    query = (
        select(Invoice)
        .where(*filters)
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    await log_audit_event(db, current_user, "list_invoices", "invoice", None, request)
    await db.commit()

    page_count = len(invoices)
    return InvoiceListResponse(
        invoices=invoices,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Get invoice by ID
    """
    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    await log_audit_event(db, current_user, "view_invoice", "invoice", invoice.id, request)
    await db.commit()

    return invoice


@router.post("/invoices/", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: InvoiceCreate,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InvoiceResponse:
    """
    Create new invoice.

    SECURITY: invoice number is generated under a Postgres advisory lock
    keyed on the practice + calendar day so concurrent inserts cannot
    produce duplicate invoice_numbers and 500 the second requester.
    """
    result = await db.execute(
        select(Patient).where(
            Patient.id == invoice_data.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Practice billing preferences supply the defaults for anything the request
    # did not specify (previously stored-but-ignored -- see
    # _get_practice_billing_prefs).
    (
        practice_tax_rate,
        invoice_prefix,
        practice_payment_terms,
        auto_send_invoices,
    ) = await _get_practice_billing_prefs(db, current_user.practice_id)

    # Generate the invoice number under the per-practice-per-day lock.
    invoice_number = await _next_invoice_number(
        db, current_user.practice_id, prefix=invoice_prefix
    )

    # Money-integrity (H3, creation-side): derived/terminal statuses cannot be
    # minted by hand. PAID / PARTIALLY_PAID must come only from recorded
    # payments, OVERDUE only from the due-date sweep, and CANCELLED is
    # terminal. The update matrix cannot guard the first write.
    requested_status = invoice_data.status or InvoiceStatus.PENDING
    if requested_status not in _CREATABLE_INVOICE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"New invoices may only be created as draft or pending "
                f"(got {requested_status.value})"
            ),
        )

    # M7 FIX: quantize to cents before storing so total always equals
    # round(subtotal) + round(tax) at the Numeric(10,2) precision.
    cent = Decimal("0.01")
    # Only fall back to the practice default when the client did not state a
    # rate at all. ``model_fields_set`` distinguishes "omitted" from an explicit
    # zero -- the schema default is Decimal('0.0'), so a plain truthiness check
    # would silently override a deliberate 0% (tax-exempt) invoice.
    if "tax_rate" in invoice_data.model_fields_set and invoice_data.tax_rate is not None:
        tax_rate = invoice_data.tax_rate
    else:
        tax_rate = practice_tax_rate
    # M4 FIX: the subtotal is computed from unit_price * quantity server-side.
    # The client-supplied `total` is informational only and is overridden, so
    # a mismatched (or future schema-loosened) total can never drive billing.
    line_items_stored = []
    for item in invoice_data.line_items:
        line_total = (Decimal(str(item.unit_price)) * Decimal(str(item.quantity))).quantize(cent, rounding=_MONEY_ROUNDING)
        stored = item.model_dump(mode='json')
        stored["total"] = str(line_total)
        line_items_stored.append(stored)
    subtotal = sum(Decimal(str(item["total"])) for item in line_items_stored).quantize(cent, rounding=_MONEY_ROUNDING)
    tax = (subtotal * tax_rate).quantize(cent, rounding=_MONEY_ROUNDING)
    total = subtotal + tax
    # L-5 FIX: populate the GST split columns so they sum to tax (were 0).
    cgst_amount, sgst_amount, igst_amount = _split_gst(tax, "N")

    # Honour the practice's configured payment terms when no explicit due date
    # was supplied (another stored-but-ignored setting).
    due_date = invoice_data.due_date
    if due_date is None:
        practice_tz = await get_practice_timezone(db, current_user.practice_id)
        due_date = business_date(practice_tz) + timedelta(days=practice_payment_terms)

    invoice = Invoice(
        practice_id=current_user.practice_id,
        patient_id=invoice_data.patient_id,
        invoice_number=invoice_number,
        status=requested_status,
        subtotal=subtotal,
        tax=tax,
        total=total,
        # H2 FIX: persist the rate so a later line_items-only edit can
        # recompute the tax instead of silently zeroing it.
        tax_rate=tax_rate,
        # Keep the GST display column (a percent) consistent with the rate.
        gst_rate=(tax_rate * 100).quantize(cent, rounding=_MONEY_ROUNDING),
        cgst_amount=cgst_amount,
        sgst_amount=sgst_amount,
        igst_amount=igst_amount,
        line_items=line_items_stored,
        due_date=due_date,
        notes=invoice_data.notes,
    )

    db.add(invoice)
    await log_audit_event(
        db, current_user, "create_invoice", "invoice", invoice.id, request,
        changes={"total": str(total), "invoice_number": invoice_number, "patient_id": str(invoice.patient_id)}
    )
    await db.commit()
    await db.refresh(invoice)

    # Auto-dispatch invoice to patient if practice configured auto_send_invoices.
    # The PatientMessage row is the durable outbox: a failed broker publish
    # cannot lose it because the periodic delivery dispatcher scans PENDING
    # rows. The invoice key makes any retried dispatch converge on one row.
    if auto_send_invoices and requested_status == InvoiceStatus.PENDING and patient.email:
        try:
            from app.models.communication import (
                MessageDirection,
                MessageStatus,
                MessageType,
                PatientMessage,
            )
            from app.core.communication_tasks import send_message_task

            msg = PatientMessage(
                practice_id=current_user.practice_id,
                patient_id=patient.id,
                message_type=MessageType.EMAIL,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                recipient_email=patient.email,
                subject=f"Invoice #{invoice_number}",
                content=(
                    f"Dear {patient.first_name},\n\nYour invoice #{invoice_number} "
                    f"for ${total:.2f} is now available. Due date: {due_date}."
                ),
                dedupe_key=f"invoice-issued:{invoice.id}",
                next_attempt_at=datetime.now(timezone.utc),
            )
            db.add(msg)
            await db.commit()
            send_message_task.delay(str(msg.id))
        except Exception as exc:
            await db.rollback()
            logger.warning(
                "Invoice %s message remains pending for dispatcher recovery: %s",
                invoice.id,
                exc,
            )

    # Reload with payments to avoid MissingGreenlet during serialization
    result = await db.execute(
        select(Invoice)
        .where(Invoice.id == invoice.id)
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
    )
    invoice = result.scalar_one()

    return invoice


# M-03 FIX: the invoice status transition matrix now lives in
# app.services.invoice_status, which is the single owner of derived state.
# PAID / PARTIALLY_PAID are functions of the payment ledger and OVERDUE is a
# function of the due date; none of the three may be set by a client. What a
# client owns is issuing a draft and cancelling.

# A brand-new invoice may only enter life as DRAFT or PENDING.
_CREATABLE_INVOICE_STATUSES = CREATABLE_STATUSES


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    invoice_data: InvoiceUpdate,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InvoiceResponse:
    """
    Update invoice
    """
    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # F22 FIX: Use model_dump() (Pydantic v2 API) instead of deprecated
    # dict() (Pydantic v1 API). On a v2 model, .dict() emits a deprecation
    # warning and may behave differently.
    update_data = invoice_data.model_dump(exclude_unset=True)

    has_payments = Decimal(str(invoice.amount_paid)) > 0

    # H3 FIX: totals are frozen once money has been posted against the
    # invoice (editing line items retroactively shrinks a paid invoice and
    # drives balance_due negative).
    if has_payments and ("line_items" in update_data or "tax_rate" in update_data):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify invoice line items after payments have been recorded",
        )

    # M-03 FIX: reject any attempt to set a derived status. OVERDUE is owned
    # by the due-date sweep, PAID / PARTIALLY_PAID by the payment ledger.
    new_status = update_data.get("status")
    if new_status is not None and new_status != invoice.status:
        error = validate_client_status_change(invoice.status, new_status)
        if error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
        if new_status == InvoiceStatus.CANCELLED and has_payments:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot cancel an invoice with recorded payments; refund them first",
            )

    if 'line_items' in update_data or 'tax_rate' in update_data:
        line_items = update_data.get('line_items', invoice.line_items)
        # H2 FIX: the rate now lives on the invoice (Invoice.tax_rate); the
        # old hasattr fallback never matched a real column and silently
        # recomputed tax as subtotal * 0 on line_items-only edits.
        tax_rate = update_data.get('tax_rate', getattr(invoice, 'tax_rate', None))
        if tax_rate is None:
            tax_rate = Decimal('0.0')

        # Handle both dict items (from model_dump) and Pydantic
        # model items. model_dump(mode='json') returns dicts with 'total'
        # as strings; we coerce to Decimal for correct arithmetic.
        def _to_decimal(val):
            if isinstance(val, Decimal):
                return val
            return Decimal(str(val))
        cent = Decimal("0.01")
        # M4 FIX: recompute every line total server-side as unit_price *
        # quantity and override the client-supplied `total`, so a mismatched
        # value can never reach the stored invoice or drive the subtotal.
        # Legacy stored items that predate unit_price/quantity keep their
        # persisted total (nothing sensible to recompute from).
        for item in line_items:
            if "unit_price" in item and "quantity" in item:
                item["total"] = str(
                    (_to_decimal(item["unit_price"]) * _to_decimal(item["quantity"])).quantize(cent, rounding=_MONEY_ROUNDING)
                )
        subtotal = sum(_to_decimal(item['total']) for item in line_items).quantize(cent, rounding=_MONEY_ROUNDING)
        tax = (subtotal * _to_decimal(tax_rate)).quantize(cent, rounding=_MONEY_ROUNDING)
        total = subtotal + tax

        invoice.subtotal = subtotal
        invoice.tax = tax
        invoice.total = total
        invoice.tax_rate = _to_decimal(tax_rate)
        invoice.gst_rate = (_to_decimal(tax_rate) * 100).quantize(cent, rounding=_MONEY_ROUNDING)
        # L-5 FIX: keep GST splits consistent on edit (were never updated).
        _cgst, _sgst, _igst = _split_gst(tax, getattr(invoice, "is_inter_state", "N"))
        invoice.cgst_amount = _cgst
        invoice.sgst_amount = _sgst
        invoice.igst_amount = _igst
        invoice.line_items = line_items

    for field, value in update_data.items():
        if field not in ['line_items', 'tax_rate']:
            setattr(invoice, field, value)

    await log_audit_event(
        db, current_user, "update_invoice", "invoice", invoice.id, request,
        changes={k: str(v) for k, v in update_data.items() if k != 'line_items'}
    )
    await db.commit()
    await db.refresh(invoice)

    return invoice


@router.delete("/invoices/{invoice_id}", response_model=dict)
async def delete_invoice(
    invoice_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete invoice (soft delete by cancelling)
    """
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # H3 FIX: an invoice with recorded payments cannot be cancelled — its
    # payments would keep counting in summaries while the voided invoice
    # shows CANCELLED with a balance.
    result = await db.execute(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
    )
    invoice = result.scalar_one()

    if Decimal(str(invoice.amount_paid)) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel an invoice with recorded payments; refund them first",
        )

    # M10 FIX: capture the previous status BEFORE mutating — the audit
    # entry used to record "cancelled" as its own previous_status.
    previous_status = (
        invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status)
    )
    invoice.status = InvoiceStatus.CANCELLED
    await log_audit_event(
        db, current_user, "cancel_invoice", "invoice", invoice.id, request,
        changes={"previous_status": previous_status, "new_status": "cancelled"}
    )
    await db.commit()

    return {"message": "Invoice cancelled successfully"}


# Payment Endpoints

@router.get("/payments/", response_model=PaymentListResponse)
async def list_payments(
    invoice_id: Optional[UUID] = Query(None),
    patient_id: Optional[UUID] = Query(None),
    status: Optional[PaymentStatus] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentListResponse:
    """
    List payments
    """
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        date_range = resolve_date_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    filters = [
        Invoice.practice_id == current_user.practice_id,
        Payment.created_at >= date_range.start_utc,
        Payment.created_at < date_range.end_utc,
    ]
    if invoice_id:
        filters.append(Payment.invoice_id == invoice_id)
    if patient_id:
        filters.append(Payment.patient_id == patient_id)
    if status:
        filters.append(Payment.status == status)

    total = (
        await db.execute(
            select(func.count(Payment.id)).join(Invoice).where(*filters)
        )
    ).scalar_one()
    query = (
        select(Payment)
        .join(Invoice)
        .where(*filters)
        .options(joinedload(Payment.invoice), joinedload(Payment.patient))
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    payments = result.scalars().all()

    await log_audit_event(db, current_user, "list_payments", "payment", None, request)
    await db.commit()

    page_count = len(payments)
    return PaymentListResponse(
        payments=payments,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )


@router.post("/payments/", response_model=PaymentResponse)
async def create_payment(
    payment_data: PaymentCreate,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PaymentResponse:
    """
    Create new payment.

    SECURITY: Locks the invoice row with ``SELECT ... FOR UPDATE`` for
    the duration of the transaction.  This prevents two concurrent
    payments from both observing ``balance_due > 0``, both inserting,
    and the invoice being over-paid without transitioning to PAID.
    """
    # Lock the invoice row for the duration of this transaction.
    # ``with_for_update()`` issues ``SELECT ... FOR UPDATE`` on Postgres.
    stmt = (
        select(Invoice)
        .where(
            Invoice.id == payment_data.invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
        .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
    )
    if row_locks_supported():
        # of=Invoice: lock only the invoice row. joinedload(Invoice.patient)
        # emits a LEFT OUTER JOIN, and PostgreSQL rejects FOR UPDATE against the
        # nullable side of an outer join outright with
        #   FeatureNotSupportedError: FOR UPDATE cannot be applied to the
        #   nullable side of an outer join
        # so this query failed every time on PostgreSQL - recording a payment
        # was broken in production - while SQLite, which has no row locking,
        # never reached the clause.
        stmt = stmt.with_for_update(of=Invoice)
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # H4 FIX: money cannot be posted to a voided or unbilled invoice — a
    # payment on a CANCELLED invoice used to grow amount_paid while the
    # status stayed CANCELLED, corrupting every reporting path.
    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT, InvoiceStatus.PAID):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice is not payable (status: {invoice.status})",
        )

    if payment_data.patient_id != invoice.patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment patient does not match invoice patient",
        )

    payment_status = payment_data.status

    # M7 FIX (manual ledger integrity): a COMPLETED payment recorded by a
    # human is money that moved outside the payment gateways, and the only
    # later reconciliation handle is its external reference (check number,
    # cash-drawer slip, UPI txn id). Require one instead of storing an
    # untraceable entry. PRODUCT DECISION (safe default) — flagged in the
    # engagement report; PENDING entries are exempt until they clear.
    if payment_status == PaymentStatus.COMPLETED and not (payment_data.transaction_id or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "A transaction ID / external reference is required to record a "
                "completed manual payment (e.g. check number, receipt number)."
            ),
        )

    if payment_status == PaymentStatus.COMPLETED:
        remaining = Decimal(str(invoice.balance_due))
        if payment_data.amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount exceeds invoice balance",
            )

    # Enforce the practice's configured payment methods. The setting was
    # stored by the settings API and echoed back to the UI, but never
    # enforced here — an owner who set acceptedPaymentMethods to ["card"]
    # could still post a check, and "upi"/"other" bypassed the gate entirely.
    # Manual ledger entries are now restricted to what the practice accepts.
    # (Provider-intiated payments via Stripe/Razorpay webhooks use their own
    # recording path and are unaffected.) A null/empty stored list falls
    # back to the historical universal default so unconfigured practices
    # keep recording cash/card/check.
    from app.models.practice import Practice as PracticeModel
    practice_result = await db.execute(
        select(PracticeModel).where(PracticeModel.id == current_user.practice_id)
    )
    practice = practice_result.scalar_one_or_none()
    accepted_methods = (
        # JSON column; runtime-guarded by the truthiness check above.
        [str(m).lower() for m in practice.accepted_payment_methods]  # type: ignore[attr-defined]
        if practice is not None and practice.accepted_payment_methods
        else ["cash", "card", "check"]
    )
    requested_method = (
        payment_data.payment_method.value
        if hasattr(payment_data.payment_method, "value")
        else str(payment_data.payment_method)
    ).lower()
    if requested_method not in accepted_methods:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Payment method '{requested_method}' is not accepted by this "
                f"practice (accepted: {', '.join(accepted_methods)})."
            ),
        )

    # M-02 FIX: a repeated transaction_id is an idempotent retry, not an
    # error. The unique constraint is the race guard, but a caller that
    # retries must get the original payment back instead of a raw 500 from
    # the IntegrityError. Check first (fast path), then handle the constraint
    # violation (correct path) for the concurrent case.
    if payment_data.transaction_id:
        # L-1 FIX: scope replay to (practice_id, transaction_id) matching
        # uq_payment_practice_transaction — the old Join(Invoice) form missed
        # foreign-practice rows and leaked existence via 409-vs-200.
        existing = await db.execute(
            select(Payment).where(
                Payment.transaction_id == payment_data.transaction_id,
                Payment.practice_id == current_user.practice_id,
            )
        )
        existing_payment = existing.scalar_one_or_none()
        if existing_payment is not None:
            if not _payment_replay_matches(existing_payment, payment_data):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Transaction ID is already used for a different payment",
                )
            logger.info(
                "Idempotent replay of payment transaction_id=%s -> payment %s",
                payment_data.transaction_id,
                existing_payment.id,
            )
            return existing_payment

    payment = Payment(
        invoice_id=invoice.id,
        patient_id=invoice.patient_id,
        practice_id=current_user.practice_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        transaction_id=payment_data.transaction_id,
        status=payment_status,
        notes=payment_data.notes,
    )

    db.add(payment)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent insert with the same transaction_id won the race.
        await db.rollback()
        if not payment_data.transaction_id:
            raise
        replay = await db.execute(
            select(Payment).where(
                Payment.transaction_id == payment_data.transaction_id,
                Payment.practice_id == current_user.practice_id,
            )
        )
        replay_payment = replay.scalar_one_or_none()
        if replay_payment is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment could not be recorded; please retry.",
            )
        if not _payment_replay_matches(replay_payment, payment_data):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction ID is already used for a different payment",
            )
        logger.info(
            "Concurrent duplicate payment transaction_id=%s resolved to payment %s",
            payment_data.transaction_id,
            replay_payment.id,
        )
        return replay_payment

    # M-03 FIX: derive the resulting invoice status from the ledger rather
    # than recomputing it inline. business_today is deliberately omitted:
    # posting a payment must never newly mark an invoice overdue.
    await db.refresh(invoice, ["payments"])
    invoice.status = derive_invoice_status(invoice)

    await log_audit_event(
        db, current_user, "create_payment", "payment", payment.id, request,
        changes={"amount": str(payment.amount), "invoice_id": str(invoice.id), "method": str(payment.payment_method)}
    )
    await db.commit()
    await db.refresh(payment)

    return payment


@router.get("/summary", response_model=BillingSummary)
async def get_billing_summary(
    request: Request,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BillingSummary:
    """
    Get billing summary
    """
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        date_range = resolve_date_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    date_filter = [
        Invoice.created_at >= date_range.start_utc,
        Invoice.created_at < date_range.end_utc,
    ]

    # Revenue figures must exclude invoices that were never billable:
    # CANCELLED invoices are not revenue, and DRAFT invoices are not yet
    # realized. They are still visible in the status breakdown below.
    billable_statuses = (
        InvoiceStatus.PENDING,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
    )

    invoice_query = select(
        func.count(Invoice.id).label('total_invoices'),
        func.sum(Invoice.total).label('total_revenue'),
        func.sum(Invoice.tax).label('total_tax'),
    ).where(
        Invoice.practice_id == current_user.practice_id,
        Invoice.status.in_(billable_statuses),
        *date_filter,
    )

    invoice_result = await db.execute(invoice_query)
    invoice_stats = invoice_result.first()

    payment_date_filter = [
        Payment.created_at >= date_range.start_utc,
        Payment.created_at < date_range.end_utc,
    ]

    payment_query = select(
        func.count(Payment.id).label('total_payments'),
        func.sum(Payment.amount - func.coalesce(Payment.refunded_amount, 0)).label('total_collected'),
    ).join(Invoice).where(
        Invoice.practice_id == current_user.practice_id,
        Invoice.status.in_(billable_statuses),
        # C1 FIX: only completed money is "collected" — failed, pending and
        # refunded amounts used to inflate total_collected and understate
        # (even negate) the outstanding balance. Refunded amounts subtract.
        # PARTIALLY_REFUNDED (2026-09) counts net-of-refund like REFUNDED.
        Payment.status.in_(
            (
                PaymentStatus.COMPLETED,
                PaymentStatus.REFUNDED,
                PaymentStatus.PARTIALLY_REFUNDED,
            )
        ),
        *payment_date_filter,
    )

    payment_result = await db.execute(payment_query)
    payment_stats = payment_result.first()

    # Outstanding is the current balance of invoices in the selected invoice
    # date window. It is not invoice revenue minus payments received in the
    # same window: that mixes two clocks and becomes negative at boundaries.
    paid_for_invoice = (
        select(func.coalesce(func.sum(
            Payment.amount - func.coalesce(Payment.refunded_amount, 0)
        ), 0))
        .where(
            Payment.invoice_id == Invoice.id,
            Payment.status.in_(
                (
                    PaymentStatus.COMPLETED,
                    PaymentStatus.REFUNDED,
                    PaymentStatus.PARTIALLY_REFUNDED,
                )
            ),
        )
        .correlate(Invoice)
        .scalar_subquery()
    )
    outstanding_query = select(
        func.sum(Invoice.total - paid_for_invoice)
    ).where(
        Invoice.practice_id == current_user.practice_id,
        Invoice.status.in_(billable_statuses),
        *date_filter,
    )
    outstanding_result = await db.execute(outstanding_query)
    outstanding_balance = _money(outstanding_result.scalar())

    status_query = select(
        Invoice.status,
        func.count(Invoice.id).label('count'),
        func.sum(Invoice.total).label('amount'),
    ).where(Invoice.practice_id == current_user.practice_id, *date_filter).group_by(Invoice.status)

    status_result = await db.execute(status_query)
    status_breakdown = status_result.all()

    pending_count_res = await db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.practice_id == current_user.practice_id,
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.DRAFT]),
            *date_filter,
        )
    )
    pending_invoices = pending_count_res.scalar() or 0

    await log_audit_event(db, current_user, "view_billing_summary", "practice", current_user.practice_id, request)
    await db.commit()

    return BillingSummary(
        total_invoices=invoice_stats.total_invoices or 0,
        pending_invoices=pending_invoices,
        total_revenue=_money(invoice_stats.total_revenue),
        total_tax=_money(invoice_stats.total_tax),
        total_payments=payment_stats.total_payments or 0,
        total_collected=_money(payment_stats.total_collected),
        outstanding_balance=outstanding_balance,
        status_breakdown=[
            {"status": status, "count": count, "amount": _money(amount)}
            for status, count, amount in status_breakdown
        ],
    )


@router.get("/reconciliation")
async def get_ledger_reconciliation(
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Surface gateway-ledger money the invoice ledger has not absorbed.

    ``payment_transactions`` (processor ledger) and ``payments`` (invoice
    ledger) are written by different paths. A completed processor charge
    whose invoice still shows a balance — or that has no invoice link at
    all — is real money the practice's reports do not yet reflect. This is
    a read-only operator view; it never moves money.
    """
    from app.models.payment import PaymentStatus as TxnStatus
    from app.models.payment import PaymentTransaction

    result = await db.execute(
        select(PaymentTransaction, Invoice)
        .outerjoin(Invoice, Invoice.id == PaymentTransaction.invoice_id)
        .options(selectinload(Invoice.payments))
        .where(
            PaymentTransaction.practice_id == current_user.practice_id,
            PaymentTransaction.status.in_(
                (TxnStatus.COMPLETED, TxnStatus.PARTIALLY_REFUNDED)
            ),
        )
        .order_by(PaymentTransaction.created_at.desc())
        .limit(200)
    )

    unapplied = []
    for txn, invoice in result.all():
        # Never expose another tenant's invoice even if a ledger row were
        # ever mis-linked across practices.
        if invoice is not None and invoice.practice_id != current_user.practice_id:
            continue
        net = Decimal(str(txn.total_amount)) - Decimal(str(txn.refunded_amount or 0))
        if net <= 0:
            continue
        if invoice is not None and Decimal(str(invoice.balance_due)) <= 0:
            continue
        unapplied.append(
            {
                "transaction_id": str(txn.id),
                "processor_transaction_id": txn.processor_transaction_id,
                "net_amount": _money(net),
                "processed_at": txn.processed_at,
                "invoice_id": str(invoice.id) if invoice else None,
                "invoice_number": invoice.invoice_number if invoice else None,
                "invoice_status": invoice.status.value if invoice else None,
                "invoice_balance_due": _money(invoice.balance_due) if invoice else None,
            }
        )

    await log_audit_event(
        db, current_user, "view_ledger_reconciliation", "practice",
        current_user.practice_id, request,
    )
    await db.commit()

    # M5 FIX: the reverse direction — completed invoice-ledger payments with
    # no linked processor transaction (PaymentTransaction.payment_id is NULL
    # and no row shares the same processor id). Manual methods are an
    # intentional mapping: a front-desk cash/check/insurance entry never
    # touches a gateway, so it is reported as "expected" rather than an
    # anomaly. Everything else (card/UPI/other) should have a processor
    # ledger row and is surfaced for operator review.
    from app.models.payment import PaymentTransaction as TxnModel

    unmatched = []
    manual_note = (
        "Manual ledger entry — no processor transaction expected "
        "(cash/check/insurance/other recorded at the front desk)"
    )
    gateway_note = (
        "No matching PaymentTransaction — verify with the processor"
    )
    manual_methods = (
        PaymentMethod.CASH,
        PaymentMethod.CHECK,
        PaymentMethod.INSURANCE,
        PaymentMethod.UPI,
        PaymentMethod.OTHER,
    )
    payments = (
        await db.execute(
            select(Payment)
            .join(Invoice)
            .where(
                Invoice.practice_id == current_user.practice_id,
                Payment.status == PaymentStatus.COMPLETED,
            )
            .options(joinedload(Payment.invoice))
            .order_by(Payment.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    for payment_row in payments:
        matched = (
            await db.execute(
                select(TxnModel.id).where(
                    TxnModel.practice_id == current_user.practice_id,
                    or_(
                        TxnModel.payment_id == payment_row.id,
                        TxnModel.processor_transaction_id == payment_row.transaction_id,
                    ),
                )
            )
        ).scalar_one_or_none()
        if matched is not None:
            continue
        method = getattr(payment_row.payment_method, "value", str(payment_row.payment_method))
        is_manual = payment_row.payment_method in manual_methods
        unmatched.append(
            {
                "payment_id": str(payment_row.id),
                "invoice_number": payment_row.invoice.invoice_number,
                "amount": _money(payment_row.amount),
                "payment_method": method,
                "transaction_id": payment_row.transaction_id,
                "expected": is_manual,
                "note": manual_note if is_manual else gateway_note,
            }
        )

    return {
        "unapplied_gateway_transactions": unapplied,
        "count": len(unapplied),
        "unmatched_completed_payments": unmatched,
        "unmatched_completed_payments_count": len(unmatched),
    }


# --- Payment Plan Endpoints ---

@router.post("/payment-plans/", response_model=PaymentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_plan(
    plan_data: PaymentPlanCreate,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PaymentPlanResponse:
    """
    Create a new installment-based payment plan
    """
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == plan_data.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    invoice_result = await db.execute(
        select(Invoice).where(
            Invoice.id == plan_data.invoice_id,
            Invoice.practice_id == current_user.practice_id,
        ).options(selectinload(Invoice.payments))
    )
    invoice = invoice_result.scalar_one_or_none()
    if not invoice or invoice.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice does not match patient",
        )
    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT, InvoiceStatus.PAID):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice is not eligible for payment plan (status: {invoice.status})",
        )
    if plan_data.total_amount > invoice.total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment plan amount cannot exceed invoice total",
        )
    if plan_data.initial_deposit > Decimal("0") and plan_data.initial_deposit > invoice.balance_due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Initial deposit ({plan_data.initial_deposit}) cannot exceed invoice balance ({invoice.balance_due})",
        )

    plan = PaymentPlan(
        practice_id=current_user.practice_id,
        patient_id=patient.id,
        invoice_id=plan_data.invoice_id,
        total_amount=plan_data.total_amount,
        initial_deposit=plan_data.initial_deposit,
        start_date=business_date(
            await get_practice_timezone(db, current_user.practice_id)
        ),
        notes=plan_data.notes,
    )
    db.add(plan)
    if plan_data.initial_deposit > Decimal("0"):
        deposit_payment = Payment(
            practice_id=current_user.practice_id,
            patient_id=patient.id,
            invoice_id=plan_data.invoice_id,
            amount=plan_data.initial_deposit,
            payment_method=PaymentMethod.OTHER,
            transaction_id=f"PLAN-DEP-{plan.id}",
            status=PaymentStatus.COMPLETED,
            notes=f"Initial deposit for payment plan {plan.id}",
        )
        invoice.payments.append(deposit_payment)
        await db.flush()

        paid_total = Decimal(str(invoice.amount_paid))
        invoice_total = Decimal(str(invoice.total or 0))
        if invoice_total > 0 and paid_total >= invoice_total:
            invoice.status = InvoiceStatus.PAID
        elif paid_total > 0 and invoice.status in (
            InvoiceStatus.PENDING,
            InvoiceStatus.OVERDUE,
            InvoiceStatus.PARTIALLY_PAID,
        ):
            invoice.status = InvoiceStatus.PARTIALLY_PAID
    await db.flush()

    num_months = plan_data.months
    financed_balance = plan.total_amount - plan.initial_deposit
    cent = Decimal("0.01")
    base_installment = (financed_balance / num_months).quantize(cent, rounding=ROUND_DOWN)
    remainder_cents = int((financed_balance - (base_installment * num_months)) / cent)

    import calendar

    def _add_months(sourcedate: date, months: int) -> date:
        month = sourcedate.month - 1 + months
        year = sourcedate.year + month // 12
        month = month % 12 + 1
        day = min(sourcedate.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    for i in range(num_months):
        installment_amount = base_installment + (cent if i < remainder_cents else Decimal("0"))
        installment = PaymentPlanInstallment(
            plan_id=plan.id,
            amount=installment_amount,
            due_date=_add_months(plan.start_date, i + 1),
            status="scheduled"
        )
        db.add(installment)

    await log_audit_event(
        db, current_user, "create_payment_plan", "payment_plan", plan.id, request,
        changes={"total_amount": str(plan.total_amount), "patient_id": str(plan.patient_id), "months": num_months}
    )
    await db.commit()
    result = await db.execute(
        select(PaymentPlan)
        .where(PaymentPlan.id == plan.id)
        .options(selectinload(PaymentPlan.installments))
    )
    return result.scalar_one()


@router.get("/payment-plans/", response_model=PaymentPlanListResponse)
async def list_payment_plans(
    patient_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentPlanListResponse:
    """
    List payment plans for the practice with bounded pagination.
    """
    filters = [PaymentPlan.practice_id == current_user.practice_id]
    if patient_id:
        filters.append(PaymentPlan.patient_id == patient_id)

    total = (
        await db.execute(select(func.count(PaymentPlan.id)).where(*filters))
    ).scalar_one()
    result = await db.execute(
        select(PaymentPlan)
        .where(*filters)
        .options(joinedload(PaymentPlan.installments))
        .order_by(PaymentPlan.created_at.desc(), PaymentPlan.id.desc())
        .offset(offset)
        .limit(limit)
    )
    plans = result.scalars().unique().all()
    page_count = len(plans)
    return PaymentPlanListResponse(
        payment_plans=plans,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )


@router.post("/payment-plans/{plan_id}/installments/{installment_id}/pay",
             response_model=PaymentPlanResponse)
async def pay_payment_plan_installment(
    plan_id: UUID,
    installment_id: UUID,
    pay_data: PaymentPlanInstallmentPay,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PaymentPlanResponse:
    """Record exactly one full, idempotent payment-plan installment."""
    # Lock the tenant-scoped parent first. This serializes all installment
    # payments for a plan, including the final COMPLETED transition.
    plan_stmt = (
        select(PaymentPlan)
        .where(
            PaymentPlan.id == plan_id,
            PaymentPlan.practice_id == current_user.practice_id,
        )
        .options(selectinload(PaymentPlan.installments))
    )
    if row_locks_supported():
        plan_stmt = plan_stmt.with_for_update()
    plan_result = await db.execute(plan_stmt)
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment plan not found")

    installment_stmt = select(PaymentPlanInstallment).where(
        PaymentPlanInstallment.id == installment_id,
        PaymentPlanInstallment.plan_id == plan.id,
    )
    if row_locks_supported():
        installment_stmt = installment_stmt.with_for_update()
    installment_result = await db.execute(installment_stmt)
    installment = installment_result.scalar_one_or_none()
    if installment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")

    if installment.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Installment has already been paid",
        )
    if plan.status == PaymentPlanStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot pay an installment on a cancelled payment plan",
        )

    cent = Decimal("0.01")
    amount = Decimal(str(installment.amount)).quantize(cent, rounding=_MONEY_ROUNDING)
    if pay_data.amount is not None and pay_data.amount.quantize(cent, rounding=_MONEY_ROUNDING) != amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Installment must be paid in the exact amount ({amount})",
        )

    transaction_id = f"PLAN-{installment_id}"
    if pay_data.transaction_id is not None and pay_data.transaction_id != transaction_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The transaction reference for a plan installment is server-defined",
        )

    # Enforce the practice's accepted payment methods (same policy as
    # POST /payments/).
    from app.models.practice import Practice as PracticeModel
    practice_result = await db.execute(
        select(PracticeModel).where(PracticeModel.id == current_user.practice_id)
    )
    practice = practice_result.scalar_one_or_none()
    accepted_methods = (
        # JSON column; runtime-guarded by the truthiness check above.
        [str(m).lower() for m in practice.accepted_payment_methods]  # type: ignore[attr-defined]
        if practice is not None and practice.accepted_payment_methods
        else ["cash", "card", "check"]
    )
    requested_method = (
        pay_data.payment_method.value
        if hasattr(pay_data.payment_method, "value")
        else str(pay_data.payment_method)
    ).lower()
    if requested_method not in accepted_methods:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Payment method '{requested_method}' is not accepted by this "
                f"practice (accepted: {', '.join(accepted_methods)})."
            ),
        )

    if not plan.invoice_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot pay installment: payment plan is missing an associated invoice",
        )

    try:
        stmt = (
            select(Invoice)
            .where(
                Invoice.id == plan.invoice_id,
                Invoice.practice_id == current_user.practice_id,
            )
            .options(joinedload(Invoice.patient), selectinload(Invoice.payments))
        )
        if row_locks_supported():
            # of=Invoice - see the note on the payment path: FOR UPDATE
            # cannot apply to the nullable side of the patient outer join.
            stmt = stmt.with_for_update(of=Invoice)
        invoice_result = await db.execute(stmt)
        invoice = invoice_result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT, InvoiceStatus.PAID):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invoice is not payable (status: {invoice.status})",
            )

        remaining = Decimal(str(invoice.balance_due))
        if amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount exceeds invoice balance",
            )

        payment = Payment(
            invoice_id=invoice.id,
            patient_id=plan.patient_id,
            practice_id=current_user.practice_id,
            amount=amount,
            payment_method=pay_data.payment_method,
            transaction_id=transaction_id,
            status=PaymentStatus.COMPLETED,
            notes=pay_data.notes or f"Payment plan installment due {installment.due_date}",
        )
        # Append through the relationship rather than db.add(): the new
        # Payment carries only the FK, so the already-loaded
        # invoice.payments collection stayed stale and the amount_paid
        # recomputation below read the PRE-payment total — first
        # installment left the invoice PENDING instead of
        # PARTIALLY_PAID, and the last one left it PARTIALLY_PAID
        # instead of PAID.
        invoice.payments.append(payment)
        # Flush is inside the duplicate guard: unique transaction races
        # normally surface here rather than at commit.
        await db.flush()

        # Status FIX: recompute from the ledger like refresh_invoice_status
        # (was a direct PAID/PARTIALLY_PAID set bypassing the ledger).
        paid_total = Decimal(str(invoice.amount_paid))
        invoice_total = Decimal(str(invoice.total))
        if paid_total >= invoice_total:
            invoice.status = InvoiceStatus.PAID
        elif paid_total > 0 and invoice.status in (
            InvoiceStatus.PENDING,
            InvoiceStatus.OVERDUE,
            InvoiceStatus.PARTIALLY_PAID,
        ):
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        from app.models.billing import InstallmentStatus as _InstStatus

        installment.status = _InstStatus.PAID.value
        installment.paid_at = datetime.now(timezone.utc)

        if all(i.status == _InstStatus.PAID.value for i in plan.installments):
            plan.status = PaymentPlanStatus.COMPLETED

        await log_audit_event(
            db, current_user, "pay_payment_plan_installment", "payment_plan", plan.id, request,
            changes={
                "installment_id": str(installment_id),
                "amount": str(amount),
                "transaction_id": transaction_id,
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This installment payment has already been recorded",
        )

    result = await db.execute(
        select(PaymentPlan)
        .where(PaymentPlan.id == plan.id)
        .options(selectinload(PaymentPlan.installments))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Refunds (Phase-1 production gap: dedicated refund workflow)
# ---------------------------------------------------------------------------


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def refund_payment(
    payment_id: UUID,
    refund_data: RefundCreate,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> RefundResponse:
    """Refund all or part of a recorded COMPLETED payment.

    The ledger already carries `refunded_amount` and the summary math
    subtracts it (`amount_paid` is net of refunds), but there was no
    server-side path to *create* a refund — clinics could only cancel an
    invoice or record new money. This closes that gap.

    Guarantees (mirroring POST /payments/):
    - Row locks the payment AND its invoice for the whole transaction so a
      concurrent payment and refund cannot interleave.
    - Never refunds more than the payment's remaining refundable balance.
    - Never takes the invoice's net collected amount below zero.
    - Recomputes both the payment status (REFUNDED / PARTIALLY_REFUNDED)
      and the invoice status (PARTIALLY_PAID / PENDING) from the ledger.
    - Full audit trail: who refunded how much of which payment, and why.
    """
    cent = Decimal("0.01")
    refund_amount = Decimal(str(refund_data.amount)).quantize(cent, rounding=_MONEY_ROUNDING)
    if refund_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Refund amount must be greater than zero",
        )

    # Lookup payment without FOR UPDATE to determine invoice_id first.
    lookup_stmt = select(Payment.invoice_id).where(
        Payment.id == payment_id,
        Payment.practice_id == current_user.practice_id,
    )
    inv_lookup_res = await db.execute(lookup_stmt)
    target_invoice_id = inv_lookup_res.scalar_one_or_none()
    if not target_invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # Lock the INVOICE row FIRST (consistent with POST /payments/ to prevent deadlock).
    invoice_stmt = (
        select(Invoice)
        .where(
            Invoice.id == target_invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
        .options(selectinload(Invoice.payments))
    )
    if row_locks_supported():
        invoice_stmt = invoice_stmt.with_for_update()
    invoice_result = await db.execute(invoice_stmt)
    invoice = invoice_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # Lock the PAYMENT row SECOND.
    payment_stmt = (
        select(Payment)
        .where(
            Payment.id == payment_id,
            Payment.practice_id == current_user.practice_id,
        )
    )
    if row_locks_supported():
        payment_stmt = payment_stmt.with_for_update()
    payment_result = await db.execute(payment_stmt)
    payment = payment_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # Only settled money can be refunded.
    if payment.status not in (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment is not refundable (status: {payment.status})",
        )

    already_refunded = Decimal(str(payment.refunded_amount or 0))
    refundable = Decimal(str(payment.amount)) - already_refunded
    if refund_amount > refundable:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Refund exceeds refundable balance ({refundable})",
        )

    # Detect processor-linked payments (Stripe/Razorpay) vs manual ledger (cash/check).
    txn_id = (payment.transaction_id or "").strip()
    is_stripe = txn_id.startswith(("pi_", "ch_"))
    is_razorpay = txn_id.startswith("pay_")

    txn_res = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.payment_id == payment.id,
            PaymentTransaction.practice_id == current_user.practice_id,
        )
    )
    txn = txn_res.scalar_one_or_none()
    if txn and txn.processor_transaction_id:
        proc_id = txn.processor_transaction_id.strip()
        if proc_id.startswith(("pi_", "ch_")):
            is_stripe = True
            if not txn_id:
                txn_id = proc_id
        elif proc_id.startswith("pay_"):
            is_razorpay = True
            if not txn_id:
                txn_id = proc_id

    gateway_refund_id = None
    if is_stripe:
        if not settings.STRIPE_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stripe API key not configured for gateway refund",
            )
        stripe_lib.api_key = settings.STRIPE_API_KEY
        try:
            refund_params = {
                "payment_intent": txn_id,
                "amount": _to_cents(refund_amount),
            }
            if refund_data.reason:
                refund_params["reason"] = "requested_by_customer"
            gateway_refund = await asyncio.to_thread(stripe_lib.Refund.create, **refund_params)
            gateway_refund_id = getattr(gateway_refund, "id", str(gateway_refund))
        except Exception as exc:
            logger.error("Stripe refund call failed for payment %s: %s", payment.id, exc)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment gateway refund failed: {str(exc)}",
            ) from exc
    elif is_razorpay:
        try:
            client = RazorpayPaymentProcessor._get_client()
            refund_params = {
                "payment_id": txn_id,
                "amount": _to_cents(refund_amount),
            }
            gateway_refund = await asyncio.to_thread(client.refund.create, refund_params)
            gateway_refund_id = gateway_refund.get("id") if isinstance(gateway_refund, dict) else str(gateway_refund)
        except Exception as exc:
            logger.error("Razorpay refund call failed for payment %s: %s", payment.id, exc)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment gateway refund failed: {str(exc)}",
            ) from exc

    # Apply the refund to the payment ledger row.
    payment.refunded_amount = already_refunded + refund_amount
    if Decimal(str(payment.refunded_amount)) >= Decimal(str(payment.amount)):
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED

    if txn:
        txn.refunded_amount = Decimal(str(txn.refunded_amount or 0)) + refund_amount
        txn.refund_reason = refund_data.reason
        if Decimal(str(txn.refunded_amount)) >= Decimal(str(txn.total_amount or txn.amount)):
            txn.status = PaymentStatus.REFUNDED.value if hasattr(PaymentStatus.REFUNDED, "value") else "refunded"
        else:
            txn.status = PaymentStatus.PARTIALLY_REFUNDED.value if hasattr(PaymentStatus.PARTIALLY_REFUNDED, "value") else "partially_refunded"

    # Recompute invoice status from the net ledger. amount_paid is net of
    # refunds; after a partial refund of a fully paid invoice it correctly
    # drops to PARTIALLY_PAID, and a full refund returns it to PENDING.
    # Note: refresh_invoice_status-style derive_invoice_status skips sticky
    # statuses (CANCELLED / PAID-on-full-refund) — here we always recompute
    # because a refund deliberately moves money *out*.
    paid_total = Decimal(str(invoice.amount_paid))
    invoice_total = Decimal(str(invoice.total or 0))
    if invoice_total > 0 and paid_total >= invoice_total:
        invoice.status = InvoiceStatus.PAID
    elif paid_total > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    else:
        today = business_date(await get_practice_timezone(db, current_user.practice_id))
        if invoice.due_date and invoice.due_date < today:
            invoice.status = InvoiceStatus.OVERDUE
        else:
            invoice.status = InvoiceStatus.PENDING

    audit_changes = {
        "invoice_number": invoice.invoice_number,
        "payment_amount": str(payment.amount),
        "refund_amount": str(refund_amount),
        "total_refunded": str(payment.refunded_amount),
        "payment_status": payment.status.value,
        "invoice_status": invoice.status.value,
        "reason": refund_data.reason,
        "manual_refund": gateway_refund_id is None,
        "note": "manual_refund: ledger-only refund recorded for manual payment"
        if gateway_refund_id is None
        else f"gateway refund processed ({gateway_refund_id})",
    }
    if gateway_refund_id:
        audit_changes["gateway_refund_id"] = gateway_refund_id

    await log_audit_event(
        db,
        current_user,
        "payment_refunded",
        "payment",
        payment.id,
        request,
        changes=audit_changes,
    )
    await db.commit()

    return RefundResponse(
        payment_id=payment.id,
        invoice_id=invoice.id,
        refunded_amount=Decimal(str(payment.refunded_amount)),
        remaining_refundable=Decimal(str(payment.amount)) - Decimal(str(payment.refunded_amount)),
        payment_status=payment.status,
        invoice_status=invoice.status,
        message=f"Refunded {refund_amount}",
    )


# ---------------------------------------------------------------------------
# Settle PENDING payments (check, UPI, or async bank transfer cleared)
# ---------------------------------------------------------------------------


@router.put("/payments/{payment_id}/settle", response_model=PaymentResponse)
async def settle_payment(
    payment_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*_BILLING_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PaymentResponse:
    """Settle an asynchronous/clearing PENDING payment (e.g. check/UPI cleared).

    Transitions payment status from PENDING to COMPLETED, checks invoice balance,
    and updates the invoice status to PARTIALLY_PAID or PAID accordingly.
    """
    lookup_stmt = select(Payment.invoice_id).where(
        Payment.id == payment_id,
        Payment.practice_id == current_user.practice_id,
    )
    inv_lookup_res = await db.execute(lookup_stmt)
    target_invoice_id = inv_lookup_res.scalar_one_or_none()
    if not target_invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    invoice_stmt = (
        select(Invoice)
        .where(
            Invoice.id == target_invoice_id,
            Invoice.practice_id == current_user.practice_id,
        )
        .options(selectinload(Invoice.payments))
    )
    if row_locks_supported():
        invoice_stmt = invoice_stmt.with_for_update()
    invoice_result = await db.execute(invoice_stmt)
    invoice = invoice_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    payment_stmt = (
        select(Payment)
        .where(
            Payment.id == payment_id,
            Payment.practice_id == current_user.practice_id,
        )
    )
    if row_locks_supported():
        payment_stmt = payment_stmt.with_for_update()
    payment_result = await db.execute(payment_stmt)
    payment = payment_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment is not pending (status: {payment.status})",
        )

    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice is not payable (status: {invoice.status})",
        )

    payment_amount = Decimal(str(payment.amount))
    balance_due = Decimal(str(invoice.balance_due))
    if payment_amount > balance_due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Settlement amount ({payment_amount}) exceeds invoice remaining balance ({balance_due})",
        )

    payment.status = PaymentStatus.COMPLETED

    await db.flush()
    paid_total = Decimal(str(invoice.amount_paid))
    invoice_total = Decimal(str(invoice.total or 0))
    if invoice_total > 0 and paid_total >= invoice_total:
        invoice.status = InvoiceStatus.PAID
    elif paid_total > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    await log_audit_event(
        db,
        current_user,
        "payment_settled",
        "payment",
        payment.id,
        request,
        changes={
            "invoice_number": invoice.invoice_number,
            "payment_amount": str(payment.amount),
            "payment_status": payment.status.value,
            "invoice_status": invoice.status.value,
        },
    )
    await db.commit()
    await db.refresh(payment)
    return payment
