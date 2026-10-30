"""
Lab Endpoints
CRUD operations for lab case management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import uuid

# L-4 FIX: single money rounding mode (HALF_UP) matching the billing ledger.
_MONEY_ROUNDING = ROUND_HALF_UP

from app.core.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.core.audit import log_audit_event
from app.core.business_time import (
    DateRangeError,
    business_date,
    day_bounds_utc,
    get_practice_timezone,
    resolve_instant_range,
)
from app.models.patient import Patient
from app.models.lab import (
    Lab,
    LabCase,
    LabInvoice,
    LabCaseStatus,
    LabCaseType,
)
from app.schemas.lab import LabInvoiceCreate, LabInvoicePayRequest
from app.api.deps import verify_csrf

router = APIRouter()

# H4 FIX: client-supplied dicts are filtered through explicit field
# allowlists before they reach the ORM. Previously raw ``setattr`` loops and
# ``**dict`` constructors let callers set arbitrary columns (id,
# case_number, is_deleted, ...) and crashed with duplicate-kwarg TypeErrors.
_LAB_WRITABLE_FIELDS = (
    "name", "contact_name", "email", "phone", "fax", "website",
    "address_line1", "address_line2", "city", "state", "zip_code",
    "account_number", "payment_terms", "services_offered",
    "is_active", "is_preferred", "notes",
)

_LAB_CASE_WRITABLE_FIELDS = (
    "case_type", "status", "description", "shade", "shade_notes",
    "teeth_involved", "sent_date", "due_date", "received_date",
    "delivered_date", "case_cost", "case_price", "patient_charge",
    "insurance_estimate", "tracking_number", "shipping_method",
    "shipping_cost", "provider_notes", "lab_notes", "internal_notes",
    "prescriptions", "impressions",
)

# Identity/lifecycle columns a client may never write on update.
_LAB_CASE_UPDATE_EXTRA_FIELDS = ("lab_id", "patient_id")


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input cannot force full scans."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _coerce_enum(enum_cls, value):
    """Coerce a client string to an enum member; None passes through."""
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(str(value))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid value '{value}' (expected one of: "
                   f"{', '.join(m.value for m in enum_cls)})",
        )


# M-08 FIX: lab cases follow a lifecycle like everything else in the system.
# Updates previously accepted arbitrary status jumps (e.g. PENDING ->
# COMPLETED, or un-cancelling a CANCELLED case), so timestamps, invoices and
# reports could disagree with the recorded workflow.
_LAB_CASE_TRANSITIONS = {
    LabCaseStatus.PENDING: {
        LabCaseStatus.SENT, LabCaseStatus.IN_PROGRESS, LabCaseStatus.CANCELLED,
        LabCaseStatus.ON_HOLD,
    },
    LabCaseStatus.SENT: {
        LabCaseStatus.IN_PROGRESS, LabCaseStatus.QUALITY_CHECK,
        LabCaseStatus.REFUSED, LabCaseStatus.CANCELLED, LabCaseStatus.ON_HOLD,
    },
    LabCaseStatus.IN_PROGRESS: {
        LabCaseStatus.QUALITY_CHECK, LabCaseStatus.READY_TO_SHIP,
        LabCaseStatus.ON_HOLD,
    },
    LabCaseStatus.QUALITY_CHECK: {
        LabCaseStatus.READY_TO_SHIP, LabCaseStatus.IN_PROGRESS,
        LabCaseStatus.ON_HOLD,
    },
    LabCaseStatus.READY_TO_SHIP: {LabCaseStatus.SHIPPED, LabCaseStatus.ON_HOLD},
    LabCaseStatus.SHIPPED: {LabCaseStatus.DELIVERED, LabCaseStatus.REFUSED},
    LabCaseStatus.DELIVERED: {LabCaseStatus.COMPLETED},
    LabCaseStatus.COMPLETED: set(),      # terminal
    LabCaseStatus.ON_HOLD: {
        LabCaseStatus.PENDING, LabCaseStatus.SENT, LabCaseStatus.IN_PROGRESS,
        LabCaseStatus.CANCELLED,
    },
    LabCaseStatus.CANCELLED: set(),      # terminal
    LabCaseStatus.REFUSED: set(),        # terminal
}


def _validate_case_transition(current: LabCaseStatus, new: LabCaseStatus) -> None:
    if current == new:
        return
    allowed = _LAB_CASE_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot change lab case status from "
                f"{current.value} to {new.value}"
            ),
        )


def _lab_to_dict(lab: Lab) -> dict:
    """Serialize a Lab vendor (excludes soft-delete internals)."""
    return {
        "id": str(lab.id),
        "practice_id": str(lab.practice_id),
        "name": lab.name,
        "contact_name": lab.contact_name,
        "email": lab.email,
        "phone": lab.phone,
        "fax": lab.fax,
        "website": lab.website,
        "address_line1": lab.address_line1,
        "address_line2": lab.address_line2,
        "city": lab.city,
        "state": lab.state,
        "zip_code": lab.zip_code,
        "account_number": lab.account_number,
        "payment_terms": lab.payment_terms,
        "services_offered": lab.services_offered,
        "is_active": lab.is_active,
        "is_preferred": lab.is_preferred,
        "notes": lab.notes,
        "created_at": lab.created_at.isoformat() if lab.created_at else None,
        "updated_at": lab.updated_at.isoformat() if lab.updated_at else None,
    }


def _money_str(value) -> str:
    """Serialize a money value as a fixed 2dp string (billing convention)."""
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=_MONEY_ROUNDING))


def _lab_invoice_to_dict(invoice: LabInvoice) -> dict:
    """Serialize a LabInvoice (excludes internal bookkeeping columns)."""
    return {
        "id": str(invoice.id),
        "practice_id": str(invoice.practice_id),
        "lab_id": str(invoice.lab_id),
        "lab_case_id": str(invoice.lab_case_id) if invoice.lab_case_id else None,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "status": invoice.status,
        "subtotal": _money_str(invoice.subtotal),
        "tax": _money_str(invoice.tax),
        "shipping": _money_str(invoice.shipping),
        "discount": _money_str(invoice.discount),
        "total": _money_str(invoice.total),
        "amount_paid": _money_str(invoice.amount_paid),
        "balance_due": _money_str(invoice.balance_due),
        "payment_date": invoice.payment_date.isoformat() if invoice.payment_date else None,
        "notes": invoice.notes,
        "terms": invoice.terms,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
    }


def _case_to_dict(case: LabCase) -> dict:
    """Serialize a LabCase to a dict for JSON response."""
    return {
        "id": str(case.id),
        "practice_id": str(case.practice_id),
        "lab_id": str(case.lab_id),
        "patient_id": str(case.patient_id),
        "provider_id": str(case.provider_id),
        "case_number": case.case_number,
        "case_type": case.case_type.value if case.case_type else None,
        "status": case.status.value if case.status else None,
        "description": case.description,
        "shade": case.shade,
        "shade_notes": case.shade_notes,
        "teeth_involved": case.teeth_involved,
        "sent_date": case.sent_date.isoformat() if case.sent_date else None,
        "due_date": case.due_date.isoformat() if case.due_date else None,
        "received_date": case.received_date.isoformat() if case.received_date else None,
        "delivered_date": case.delivered_date.isoformat() if case.delivered_date else None,
        "case_cost": str(case.case_cost) if case.case_cost is not None else None,
        "case_price": str(case.case_price) if case.case_price is not None else None,
        "patient_charge": str(case.patient_charge) if case.patient_charge is not None else None,
        "insurance_estimate": str(case.insurance_estimate) if case.insurance_estimate is not None else None,
        "tracking_number": case.tracking_number,
        "shipping_method": case.shipping_method,
        "shipping_cost": str(case.shipping_cost) if case.shipping_cost is not None else None,
        "is_deleted": case.is_deleted,
        "provider_notes": case.provider_notes,
        "lab_notes": case.lab_notes,
        "internal_notes": case.internal_notes,
        "prescriptions": case.prescriptions,
        "impressions": case.impressions,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


# Lab Endpoints

@router.get("/vendors/")
async def list_labs(
    request: Request,
    search: Optional[str] = Query(None, description="Search by name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_preferred: Optional[bool] = Query(None, description="Filter by preferred"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List dental labs
    """
    query = select(Lab).where(
        Lab.practice_id == current_user.practice_id,
        Lab.is_deleted.is_(False)
    )

    if is_active is not None:
        query = query.where(Lab.is_active == is_active)

    if is_preferred is not None:
        query = query.where(Lab.is_preferred == is_preferred)

    if search:
        # Parameterized + wildcard-escaped (L2): '%'/'_' in user input are
        # treated literally instead of forcing full-table scans.
        search_pattern = f"%{_escape_like(search)}%"
        query = query.where(Lab.name.ilike(search_pattern, escape="\\"))

    query = query.order_by(Lab.name)

    result = await db.execute(query)
    labs = result.scalars().all()

    # HIPAA: Log lab vendor list access
    await log_audit_event(
        db, current_user, "list_labs", "lab", None, request
    )
    await db.commit()

    return {"labs": [_lab_to_dict(item) for item in labs], "count": len(labs)}


@router.post("/vendors/")
async def create_lab(
    lab_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new lab vendor
    """
    fields = {k: v for k, v in lab_data.items() if k in _LAB_WRITABLE_FIELDS}
    if not fields.get("name"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name is required",
        )
    lab = Lab(
        practice_id=current_user.practice_id,
        **fields
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)

    return _lab_to_dict(lab)


@router.put("/vendors/{vendor_id}")
async def update_lab(
    vendor_id: uuid.UUID,
    lab_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update a lab vendor (tenant-scoped)."""
    result = await db.execute(
        select(Lab).where(
            Lab.id == vendor_id,
            Lab.practice_id == current_user.practice_id,
            Lab.is_deleted.is_(False),
        )
    )
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")

    for field in _LAB_WRITABLE_FIELDS:
        if field in lab_data:
            setattr(lab, field, lab_data[field])

    await db.commit()
    await db.refresh(lab)
    return _lab_to_dict(lab)


@router.delete("/vendors/{vendor_id}")
async def delete_lab(
    request: Request,
    vendor_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Soft-delete a lab vendor (HIPAA: preserve clinical attribution)."""
    result = await db.execute(
        select(Lab).where(
            Lab.id == vendor_id,
            Lab.practice_id == current_user.practice_id,
            Lab.is_deleted.is_(False),
        )
    )
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")

    lab.is_deleted = True
    lab.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    await log_audit_event(
        db, current_user, "delete_lab", "lab", lab.id, request,
        changes={"deleted_at": str(lab.deleted_at)},
    )
    await db.commit()

    return {"message": "Lab vendor deleted successfully"}



# Lab Case Endpoints

@router.get("/cases/")
async def list_lab_cases(
    request: Request,
    status: Optional[LabCaseStatus] = Query(None, description="Filter by status"),
    case_type: Optional[LabCaseType] = Query(None, description="Filter by type"),
    lab_id: Optional[str] = Query(None, description="Filter by lab"),
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List lab cases in a bounded practice-local instant range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        instant_range = resolve_instant_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        # ``status`` is a legacy public query parameter in this handler.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Explicit date filters keep their legacy sent-date semantics. With no
    # filter, include unsent cases by their creation instant so the bounded
    # default list remains operationally useful.
    case_instant = LabCase.sent_date
    if start_date is None and end_date is None:
        case_instant = func.coalesce(LabCase.sent_date, LabCase.created_at)

    filters = [
        LabCase.practice_id == current_user.practice_id,
        LabCase.is_deleted.is_(False),
        case_instant >= instant_range.start_utc,
        case_instant < instant_range.end_utc,
    ]
    if status:
        filters.append(LabCase.status == status)
    if case_type:
        filters.append(LabCase.case_type == case_type)
    if lab_id:
        filters.append(LabCase.lab_id == lab_id)
    if patient_id:
        filters.append(LabCase.patient_id == patient_id)

    total = (
        await db.execute(select(func.count(LabCase.id)).where(*filters))
    ).scalar_one()
    query = (
        select(LabCase)
        .where(*filters)
        .order_by(case_instant.desc(), LabCase.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    cases = result.scalars().all()

    # HIPAA: Log lab cases list access
    await log_audit_event(
        db, current_user, "list_lab_cases", "lab_case", None, request
    )
    await db.commit()

    page_count = len(cases)
    return {
        "cases": [_case_to_dict(c) for c in cases],
        "count": page_count,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + page_count if offset + page_count < total else None,
    }


@router.get("/cases/{case_id}")
async def get_lab_case(
    request: Request,
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get lab case by ID
    """
    result = await db.execute(
        select(LabCase).where(
            LabCase.id == case_id,
            LabCase.practice_id == current_user.practice_id,
            LabCase.is_deleted.is_(False)
        )
    )
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab case not found",
        )

    # HIPAA: Log lab case access
    await log_audit_event(
        db, current_user, "view_lab_case", "lab_case", case.id, request
    )
    await db.commit()

    return _case_to_dict(case)


@router.post("/cases/")
async def create_lab_case(
    case_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new lab case
    """
    # H3 FIX: Verify lab exists and belongs to current user's practice
    lab_id_val = case_data.get("lab_id")
    lab_id = uuid.UUID(lab_id_val) if isinstance(lab_id_val, str) else lab_id_val
    if not lab_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lab_id is required",
        )
    lab_res = await db.execute(
        select(Lab).where(
            Lab.id == lab_id,
            Lab.practice_id == current_user.practice_id,
            Lab.is_deleted.is_(False),
        )
    )
    if not lab_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab not found",
        )

    # Verify patient exists
    patient_id_str = case_data.get("patient_id")
    patient_id = uuid.UUID(patient_id_str) if isinstance(patient_id_str, str) else patient_id_str
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Generate case number under a per-practice advisory lock. The calendar
    # day and range predicates are based on the practice timezone, not the
    # database host's UTC date.
    from app.core.database import row_locks_supported

    is_postgres = row_locks_supported()
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    today = business_date(practice_tz)
    start_utc, end_utc = day_bounds_utc(practice_tz, today)

    if is_postgres:
        day_key = int(today.strftime("%Y%m%d"))
        practice_int = int.from_bytes(
            current_user.practice_id.bytes[:8], byteorder="big", signed=False
        ) & 0x7FFFFFFFFFFFFFFF
        lock_key = (practice_int ^ day_key) & 0x7FFFFFFFFFFFFFFF
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    count_result = await db.execute(
        select(func.count(LabCase.id)).where(
            LabCase.practice_id == current_user.practice_id,
            LabCase.created_at >= start_utc,
            LabCase.created_at < end_utc,
        )
    )
    count = count_result.scalar() or 0
    seq = count + 1
    while seq < count + 10000:
        candidate = f"CASE-{today.strftime('%Y%m%d')}-{seq:04d}"
        exists = await db.execute(
            select(LabCase.id).where(
                LabCase.practice_id == current_user.practice_id,
                LabCase.case_number == candidate,
            )
        )
        if exists.scalar_one_or_none() is None:
            case_number = candidate
            break
        seq += 1
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate a case number",
        )

    # H4 FIX: filter to writable fields only. provider_id/case_number/
    # practice_id are server-set; unknown keys are ignored instead of
    # crashing with a duplicate-kwarg TypeError.
    fields = {k: v for k, v in case_data.items() if k in _LAB_CASE_WRITABLE_FIELDS}
    if "case_type" not in fields or fields.get("case_type") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="case_type is required",
        )
    fields["case_type"] = _coerce_enum(LabCaseType, fields.get("case_type"))
    fields["status"] = _coerce_enum(LabCaseStatus, fields.get("status", LabCaseStatus.PENDING))

    lab_case = LabCase(
        practice_id=current_user.practice_id,
        lab_id=lab_id,
        patient_id=patient.id,
        provider_id=current_user.id,
        case_number=case_number,
        **fields
    )
    db.add(lab_case)
    await db.commit()
    await db.refresh(lab_case)

    return _case_to_dict(lab_case)


@router.put("/cases/{case_id}")
async def update_lab_case(
    case_id: uuid.UUID,
    case_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Update lab case
    """
    result = await db.execute(
        select(LabCase).where(
            LabCase.id == case_id,
            LabCase.practice_id == current_user.practice_id,
            LabCase.is_deleted.is_(False),
        )
    )
    lab_case = result.scalar_one_or_none()

    if not lab_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab case not found",
        )

    # H4 FIX: allowlist update fields. Identity/lifecycle columns (id,
    # practice_id, case_number, provider_id, is_deleted, deleted_at,
    # created_at, updated_at) are never client-writable. If the payload
    # re-points the case at another lab or patient, that reference is
    # validated against this practice first.
    for field in (*_LAB_CASE_WRITABLE_FIELDS, *_LAB_CASE_UPDATE_EXTRA_FIELDS):
        if field not in case_data:
            continue
        value = case_data[field]
        if field == "case_type":
            value = _coerce_enum(LabCaseType, value)
        elif field == "status":
            value = _coerce_enum(LabCaseStatus, value)
            # M-08 FIX: enforce the lifecycle (see _LAB_CASE_TRANSITIONS).
            if value is not None:
                _validate_case_transition(lab_case.status, value)
        elif field == "lab_id":
            lab_res = await db.execute(
                select(Lab.id).where(
                    Lab.id == value,
                    Lab.practice_id == current_user.practice_id,
                    Lab.is_deleted.is_(False),
                )
            )
            if lab_res.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
        elif field == "patient_id":
            patient_res = await db.execute(
                select(Patient.id).where(
                    Patient.id == value,
                    Patient.practice_id == current_user.practice_id,
                )
            )
            if patient_res.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        setattr(lab_case, field, value)

    # Auto-update timestamps based on status
    if lab_case.status == LabCaseStatus.SHIPPED and not lab_case.delivered_date:
        lab_case.delivered_date = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(lab_case)

    return _case_to_dict(lab_case)


@router.delete("/cases/{case_id}")
async def delete_lab_case(
    request: Request,
    case_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete lab case
    """
    result = await db.execute(
        select(LabCase).where(
            LabCase.id == case_id,
            LabCase.practice_id == current_user.practice_id,
            LabCase.is_deleted.is_(False),
        )
    )
    lab_case = result.scalar_one_or_none()

    if not lab_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab case not found",
        )

    # HIPAA HARDENING: Use soft-delete to preserve clinical audit trail
    lab_case.is_deleted = True
    lab_case.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Lab case deleted successfully"}


# Lab Invoice Endpoints

@router.get("/invoices/")
async def list_lab_invoices(
    status: Optional[str] = Query(None, description="Filter by status"),
    lab_id: Optional[str] = Query(None, description="Filter by lab"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List lab invoices in a bounded practice-local instant range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        instant_range = resolve_instant_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        # ``status`` is a legacy public query parameter in this handler.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filters = [
        LabInvoice.practice_id == current_user.practice_id,
        LabInvoice.invoice_date >= instant_range.start_utc,
        LabInvoice.invoice_date < instant_range.end_utc,
    ]
    if status:
        filters.append(LabInvoice.status == status)
    if lab_id:
        filters.append(LabInvoice.lab_id == lab_id)

    total = (
        await db.execute(select(func.count(LabInvoice.id)).where(*filters))
    ).scalar_one()
    query = (
        select(LabInvoice)
        .where(*filters)
        .order_by(LabInvoice.invoice_date.desc(), LabInvoice.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    # HIPAA: Log lab invoices list access
    await log_audit_event(
        db, current_user, "list_lab_invoices", "lab_invoice", None, request
    )
    await db.commit()

    page_count = len(invoices)
    return {
        "invoices": [_lab_invoice_to_dict(i) for i in invoices],
        "count": page_count,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + page_count if offset + page_count < total else None,
    }


@router.get("/invoices/{invoice_id}")
async def get_lab_invoice(
    request: Request,
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get lab invoice by ID
    """
    result = await db.execute(
        select(LabInvoice).where(
            LabInvoice.id == invoice_id,
            LabInvoice.practice_id == current_user.practice_id,
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab invoice not found",
        )

    # HIPAA: Log lab invoice access
    await log_audit_event(
        db, current_user, "view_lab_invoice", "lab_invoice", invoice.id, request
    )
    await db.commit()

    return _lab_invoice_to_dict(invoice)


# L-2 FIX: lab invoice numbers are per-practice unique
# (uq_lab_invoice_practice_number), so allocation uses a per-practice
# advisory lock like invoice/claim/case numbers. The visible day prefix and
# the per-practice count are both based on the practice-local business day.
async def _next_lab_invoice_number(db: AsyncSession, practice_id: uuid.UUID) -> str:
    from app.core.database import row_locks_supported

    is_postgres = row_locks_supported()
    practice_tz = await get_practice_timezone(db, practice_id)
    today = business_date(practice_tz)
    start_utc, end_utc = day_bounds_utc(practice_tz, today)

    if is_postgres:
        day_key = int(today.strftime("%Y%m%d"))
        try:
            practice_int = int(str(practice_id).replace("-", "")[:15], 16)
        except ValueError:
            practice_int = 0
        # Per-practice lock: different practices no longer serialize on the
        # shared date prefix now that numbers are namespaced per practice.
        lock_key = (practice_int ^ day_key ^ 0x4C4142494E560000) & 0x7FFFFFFFFFFFFFFF
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    day_prefix = today.strftime("%Y%m%d")
    count_q = select(func.count(LabInvoice.id)).where(
        LabInvoice.practice_id == practice_id,
        LabInvoice.created_at >= start_utc,
        LabInvoice.created_at < end_utc,
    )
    count = (await db.execute(count_q)).scalar() or 0
    seq = count + 1
    while seq < count + 10000:
        candidate = f"LABINV-{day_prefix}-{seq:04d}"
        exists = await db.execute(
            select(LabInvoice.id).where(
                LabInvoice.invoice_number == candidate,
                LabInvoice.practice_id == practice_id,
            )
        )
        if exists.scalar_one_or_none() is None:
            return candidate
        seq += 1
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate a lab invoice number",
    )


@router.post("/invoices/", status_code=status.HTTP_201_CREATED)
async def create_lab_invoice(
    request: Request,
    invoice_data: LabInvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Create a lab invoice.

    ``total`` is always computed server-side from the line components (never
    trusted from the client) with Decimal arithmetic, so the stored total is
    exact to the cent and equal to subtotal + tax + shipping - discount.
    """
    lab_res = await db.execute(
        select(Lab).where(
            Lab.id == invoice_data.lab_id,
            Lab.practice_id == current_user.practice_id,
            Lab.is_deleted.is_(False),
        )
    )
    if not lab_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")

    if invoice_data.lab_case_id:
        case_res = await db.execute(
            select(LabCase).where(
                LabCase.id == invoice_data.lab_case_id,
                # M-08 FIX: the case must belong to the SAME lab as the
                # invoice -- a practice-scoped case from another lab's
                # workflow could otherwise be billed here.
                LabCase.lab_id == invoice_data.lab_id,
                LabCase.practice_id == current_user.practice_id,
                LabCase.is_deleted.is_(False),
            )
        )
        if not case_res.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab case not found")

    invoice_number = await _next_lab_invoice_number(db, current_user.practice_id)

    cent = Decimal("0.01")
    subtotal = invoice_data.subtotal.quantize(cent, rounding=_MONEY_ROUNDING)
    tax = invoice_data.tax.quantize(cent, rounding=_MONEY_ROUNDING)
    shipping = invoice_data.shipping.quantize(cent, rounding=_MONEY_ROUNDING)
    discount = invoice_data.discount.quantize(cent, rounding=_MONEY_ROUNDING)
    if discount > (subtotal + tax + shipping):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount cannot exceed invoice subtotal + tax + shipping",
        )
    total = (subtotal + tax + shipping - discount).quantize(cent, rounding=_MONEY_ROUNDING)

    invoice = LabInvoice(
        practice_id=current_user.practice_id,
        lab_id=invoice_data.lab_id,
        lab_case_id=invoice_data.lab_case_id,
        invoice_number=invoice_number,
        due_date=invoice_data.due_date,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        discount=discount,
        total=total,
        status="pending",
        amount_paid=Decimal("0"),
        notes=invoice_data.notes,
        terms=invoice_data.terms,
    )
    db.add(invoice)

    await log_audit_event(
        db, current_user, "create_lab_invoice", "lab_invoice", invoice.id, request,
        changes={"invoice_number": invoice_number, "total": str(total), "lab_id": str(invoice_data.lab_id)},
    )
    await db.commit()
    await db.refresh(invoice)

    return _lab_invoice_to_dict(invoice)


@router.post("/invoices/{invoice_id}/pay")
async def pay_lab_invoice(
    request: Request,
    invoice_id: uuid.UUID,
    pay_data: LabInvoicePayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Record or replay an idempotent lab-invoice payment."""
    from sqlalchemy.exc import IntegrityError

    from app.core.database import row_locks_supported
    from app.models.lab import LabInvoicePayment

    amount = pay_data.amount.quantize(Decimal("0.01"), rounding=_MONEY_ROUNDING)
    transaction_id = pay_data.transaction_id.strip()

    stmt = select(LabInvoice).where(
        LabInvoice.id == invoice_id,
        LabInvoice.practice_id == current_user.practice_id,
    )
    if row_locks_supported():
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab invoice not found")

    # The invoice lock serializes retries for the same invoice. Replaying the
    # same tenant/invoice/amount succeeds without mutating the aggregate.
    existing_result = await db.execute(
        select(LabInvoicePayment).where(
            LabInvoicePayment.practice_id == current_user.practice_id,
            LabInvoicePayment.transaction_id == transaction_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if (
            existing.lab_invoice_id == invoice.id
            and Decimal(str(existing.amount)).quantize(Decimal("0.01"), rounding=_MONEY_ROUNDING) == amount
        ):
            return _lab_invoice_to_dict(invoice)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction reference is already bound to a different payment",
        )

    if invoice.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot pay a cancelled lab invoice",
        )

    total = Decimal(str(invoice.total or 0))
    already_paid = Decimal(str(invoice.amount_paid or 0))
    remaining = total - already_paid

    if amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment amount exceeds the remaining balance ({remaining})",
        )

    payment_date = pay_data.payment_date or datetime.now(timezone.utc)
    ledger_entry = LabInvoicePayment(
        practice_id=current_user.practice_id,
        lab_invoice_id=invoice.id,
        amount=amount,
        transaction_id=transaction_id,
        payment_date=payment_date,
        notes=pay_data.notes,
        recorded_by_id=current_user.id,
    )
    db.add(ledger_entry)

    try:
        # Detect a cross-invoice transaction-key race before touching the
        # cached aggregate. Commit remains guarded for deferred constraints.
        await db.flush()

        new_paid = (already_paid + amount).quantize(Decimal("0.01"), rounding=_MONEY_ROUNDING)
        invoice.amount_paid = new_paid
        invoice.payment_date = payment_date
        if invoice.notes and pay_data.notes:
            invoice.notes = f"{invoice.notes}\n{pay_data.notes}"
        elif pay_data.notes:
            invoice.notes = pay_data.notes

        if new_paid >= total:
            invoice.status = "paid"
        elif new_paid > 0:
            invoice.status = "partial"

        await log_audit_event(
            db, current_user, "pay_lab_invoice", "lab_invoice", invoice.id, request,
            changes={
                "amount": str(amount),
                "new_amount_paid": str(new_paid),
                "status": invoice.status,
                "transaction_id": transaction_id,
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner_result = await db.execute(
            select(LabInvoicePayment).where(
                LabInvoicePayment.practice_id == current_user.practice_id,
                LabInvoicePayment.transaction_id == transaction_id,
            )
        )
        winner = winner_result.scalar_one_or_none()
        if (
            winner is not None
            and winner.lab_invoice_id == invoice_id
            and Decimal(str(winner.amount)).quantize(Decimal("0.01"), rounding=_MONEY_ROUNDING) == amount
        ):
            refreshed_result = await db.execute(
                select(LabInvoice).where(
                    LabInvoice.id == invoice_id,
                    LabInvoice.practice_id == current_user.practice_id,
                )
            )
            return _lab_invoice_to_dict(refreshed_result.scalar_one())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction reference is already bound to a different payment",
        )

    await db.refresh(invoice)
    return _lab_invoice_to_dict(invoice)


# Lab Reports Endpoints

@router.get("/reports/summary")
async def get_lab_summary(
    request: Request,
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get lab summary statistics for a bounded practice-local range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        instant_range = resolve_instant_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Match the list behavior: explicit date filters target sent_date, while
    # the default bounded window includes newly created unsent cases.
    case_instant = LabCase.sent_date
    if start_date is None and end_date is None:
        case_instant = func.coalesce(LabCase.sent_date, LabCase.created_at)

    query = select(LabCase).where(
        LabCase.practice_id == current_user.practice_id,
        LabCase.is_deleted.is_(False),
        case_instant >= instant_range.start_utc,
        case_instant < instant_range.end_utc,
    )
    result = await db.execute(query)
    cases = result.scalars().all()

    # Calculate stats
    total = len(cases)
    pending = sum(1 for c in cases if c.status == LabCaseStatus.PENDING)
    in_progress = sum(1 for c in cases if c.status == LabCaseStatus.IN_PROGRESS)
    completed = sum(1 for c in cases if c.status == LabCaseStatus.COMPLETED)

    # Calculate costs using Decimal to avoid binary float precision drift
    cent = Decimal("0.01")
    total_cost = sum((Decimal(str(c.case_cost or 0)) for c in cases), Decimal("0")).quantize(cent, rounding=_MONEY_ROUNDING)
    total_charged = sum((Decimal(str(c.patient_charge or 0)) for c in cases), Decimal("0")).quantize(cent, rounding=_MONEY_ROUNDING)

    # HIPAA: Log lab summary access
    await log_audit_event(
        db, current_user, "view_lab_summary", "lab_report", None, request
    )
    await db.commit()

    return {
        "total_cases": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "total_cost": float(total_cost),
        "total_charged": float(total_charged),
    }