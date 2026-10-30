"""
Referral Endpoints
CRUD operations for referral management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional
import uuid
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.core.email import email_service
from app.api.deps import get_current_user, require_role, verify_csrf
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
from app.models.referral import (
    ReferralSource1,
    Referral,
    ReferralCommunication,
    ReferralStatus,
    ReferralType,
    ReferralSource,
)

router = APIRouter()

# H4 FIX: explicit writable-field allowlists for every client-dict endpoint
# (previously raw **dict constructors and setattr loops).
_SOURCE_WRITABLE_FIELDS = (
    "name", "source_type", "contact_name", "email", "phone", "address",
    "specialty", "license_number", "is_active", "is_track_referrals", "notes",
)

_REFERRAL_WRITABLE_FIELDS = (
    "referral_source_id", "target_practice_id", "is_internal",
    "referral_type", "status", "reason", "clinical_notes",
    "specialist_name", "specialist_address", "specialist_phone",
    "specialist_fax", "appointment_date", "outcome",
    "follow_up_required", "follow_up_notes", "referral_fee",
    "referral_received", "payment_date", "is_urgent", "urgent_reason",
    "attachments",
)

_COMMUNICATION_WRITABLE_FIELDS = (
    "communication_type", "subject", "content", "direction", "related_to",
)

# M-09 FIX: referral status transition matrix. The update path previously
# accepted any enum value, so a COMPLETED or CANCELLED referral could be
# reopened and a referral could jump straight to COMPLETED without ever being
# sent. Terminal states are terminal.
_REFERRAL_TRANSITIONS = {
    ReferralStatus.PENDING: {ReferralStatus.SENT, ReferralStatus.CANCELLED},
    ReferralStatus.SENT: {
        ReferralStatus.SCHEDULED,
        ReferralStatus.COMPLETED,
        ReferralStatus.NO_SHOW,
        ReferralStatus.CANCELLED,
    },
    ReferralStatus.SCHEDULED: {
        ReferralStatus.COMPLETED,
        ReferralStatus.NO_SHOW,
        ReferralStatus.CANCELLED,
    },
    ReferralStatus.NO_SHOW: {ReferralStatus.SCHEDULED, ReferralStatus.CANCELLED},
    # Terminal.
    ReferralStatus.COMPLETED: set(),
    ReferralStatus.CANCELLED: set(),
}


async def _validate_referral_references(
    db: AsyncSession,
    current_user: User,
    fields: dict,
) -> None:
    """M-09 FIX: prove referral_source_id / target_practice_id belong here.

    Both were copied straight from the request into the row. A referral source
    is a per-practice configuration row, so an unvalidated id leaked another
    tenant's source into this practice's reporting. ``target_practice_id`` is a
    foreign key to *another* practice by design (that is what an outbound
    referral is), but it must still be a practice this user is allowed to name
    -- otherwise a caller can enumerate practice ids and assert a relationship
    with any of them.
    """
    source_id = fields.get("referral_source_id")
    if source_id:
        source = (
            await db.execute(
                select(ReferralSource1).where(
                    ReferralSource1.id == source_id,
                    ReferralSource1.practice_id == current_user.practice_id,
                    ReferralSource1.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referral source not found or access denied",
            )

    target_id = fields.get("target_practice_id")
    if target_id:
        # Permitted targets: our own practice (an internal referral), or a
        # sibling practice in the same practice group. Anything else is not a
        # relationship this user can assert.
        from app.models.practice import Practice as PracticeModel

        own = (
            await db.execute(
                select(PracticeModel).where(
                    PracticeModel.id == current_user.practice_id
                )
            )
        ).scalar_one_or_none()
        allowed = str(target_id) == str(current_user.practice_id)
        if not allowed and own is not None and own.group_id:
            sibling = (
                await db.execute(
                    select(PracticeModel.id).where(
                        PracticeModel.id == target_id,
                        PracticeModel.group_id == own.group_id,
                    )
                )
            ).scalar_one_or_none()
            allowed = sibling is not None
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Target practice not found or not in your practice group. "
                    "Use the specialist_* fields for external referrals."
                ),
            )


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


def _source_to_dict(source: ReferralSource1) -> dict:
    return {
        "id": str(source.id),
        "practice_id": str(source.practice_id),
        "name": source.name,
        "source_type": source.source_type.value if source.source_type else None,
        "contact_name": source.contact_name,
        "email": source.email,
        "phone": source.phone,
        "address": source.address,
        "specialty": source.specialty,
        "license_number": source.license_number,
        "is_active": source.is_active,
        "is_track_referrals": source.is_track_referrals,
        "notes": source.notes,
        "total_referrals": source.total_referrals,
        "successful_referrals": source.successful_referrals,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


def _referral_to_dict(referral: Referral) -> dict:
    patient = referral.patient
    return {
        "id": str(referral.id),
        "practice_id": str(referral.practice_id),
        "patient_id": str(referral.patient_id),
        "patient_name": f"{patient.first_name} {patient.last_name}" if patient else None,
        "referring_provider_id": str(referral.referring_provider_id),
        "referral_source_id": str(referral.referral_source_id) if referral.referral_source_id else None,
        "target_practice_id": str(referral.target_practice_id) if referral.target_practice_id else None,
        "is_internal": referral.is_internal,
        "referral_number": referral.referral_number,
        "referral_type": referral.referral_type.value if referral.referral_type else None,
        "status": referral.status.value if referral.status else None,
        "reason": referral.reason,
        "clinical_notes": referral.clinical_notes,
        "specialist_name": referral.specialist_name,
        "specialist_address": referral.specialist_address,
        "specialist_phone": referral.specialist_phone,
        "specialist_fax": referral.specialist_fax,
        "referral_date": referral.referral_date.isoformat() if referral.referral_date else None,
        "appointment_date": referral.appointment_date.isoformat() if referral.appointment_date else None,
        "completed_date": referral.completed_date.isoformat() if referral.completed_date else None,
        "completed_at": referral.completed_at.isoformat() if referral.completed_at else None,
        "outcome": referral.outcome,
        "follow_up_required": referral.follow_up_required,
        "follow_up_notes": referral.follow_up_notes,
        "referral_fee": str(referral.referral_fee) if referral.referral_fee is not None else None,
        "referral_received": referral.referral_received,
        "payment_date": referral.payment_date.isoformat() if referral.payment_date else None,
        "is_urgent": referral.is_urgent,
        "urgent_reason": referral.urgent_reason,
        "attachments": referral.attachments,
        "created_at": referral.created_at.isoformat() if referral.created_at else None,
        "updated_at": referral.updated_at.isoformat() if referral.updated_at else None,
    }


def _communication_to_dict(comm: ReferralCommunication) -> dict:
    return {
        "id": str(comm.id),
        "referral_id": str(comm.referral_id),
        "user_id": str(comm.user_id) if comm.user_id else None,
        "communication_type": comm.communication_type,
        "subject": comm.subject,
        "content": comm.content,
        "direction": comm.direction,
        "related_to": comm.related_to,
        "created_at": comm.created_at.isoformat() if comm.created_at else None,
    }


# Referral Source Endpoints

@router.get("/sources/")
async def list_referral_sources(
    search: Optional[str] = Query(None, description="Search by name"),
    source_type: Optional[ReferralSource] = Query(None, description="Filter by source type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List referral sources
    """
    query = select(ReferralSource1).where(
        ReferralSource1.practice_id == current_user.practice_id,
        ReferralSource1.is_deleted.is_(False),
    )

    if is_active is not None:
        query = query.where(ReferralSource1.is_active == is_active)

    if source_type:
        query = query.where(ReferralSource1.source_type == source_type)

    if search:
        # Parameterized + wildcard-escaped (L2)
        search_pattern = f"%{_escape_like(search)}%"
        query = query.where(ReferralSource1.name.ilike(search_pattern, escape="\\"))

    query = query.order_by(ReferralSource1.name)

    result = await db.execute(query)
    sources = result.scalars().all()

    return {"sources": [_source_to_dict(s) for s in sources], "count": len(sources)}


@router.post("/sources/")
async def create_referral_source(
    source_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new referral source
    """
    fields = {k: v for k, v in source_data.items() if k in _SOURCE_WRITABLE_FIELDS}
    if not fields.get("name"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name is required",
        )
    fields["source_type"] = _coerce_enum(ReferralSource, fields.get("source_type"))
    if fields["source_type"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_type is required",
        )

    source = ReferralSource1(
        practice_id=current_user.practice_id,
        **fields
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return _source_to_dict(source)


@router.put("/sources/{source_id}")
async def update_referral_source(
    source_id: uuid.UUID,
    source_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update a referral source (tenant-scoped)."""
    result = await db.execute(
        select(ReferralSource1).where(
            ReferralSource1.id == source_id,
            ReferralSource1.practice_id == current_user.practice_id,
            ReferralSource1.is_deleted.is_(False),
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral source not found")

    for field in _SOURCE_WRITABLE_FIELDS:
        if field not in source_data:
            continue
        value = source_data[field]
        if field == "source_type":
            value = _coerce_enum(ReferralSource, value)
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)
    return _source_to_dict(source)


@router.delete("/sources/{source_id}")
async def delete_referral_source(
    source_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Soft-delete a referral source (HIPAA: preserve referral attribution)."""
    result = await db.execute(
        select(ReferralSource1).where(
            ReferralSource1.id == source_id,
            ReferralSource1.practice_id == current_user.practice_id,
            ReferralSource1.is_deleted.is_(False),
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral source not found")

    source.is_deleted = True
    source.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Referral source deleted successfully"}


# Referral Endpoints

@router.get("/")
async def list_referrals(
    status: Optional[ReferralStatus] = Query(None, description="Filter by status"),
    referral_type: Optional[ReferralType] = Query(None, description="Filter by type"),
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    source_id: Optional[str] = Query(None, description="Filter by source"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List referrals in a bounded practice-local instant range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        instant_range = resolve_instant_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        # ``status`` is a legacy public query parameter in this handler.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filters = [
        Referral.practice_id == current_user.practice_id,
        Referral.is_deleted.is_(False),
        Referral.referral_date >= instant_range.start_utc,
        Referral.referral_date < instant_range.end_utc,
    ]
    if status:
        filters.append(Referral.status == status)
    if referral_type:
        filters.append(Referral.referral_type == referral_type)
    if patient_id:
        filters.append(Referral.patient_id == patient_id)
    if source_id:
        filters.append(Referral.referral_source_id == source_id)

    total = (
        await db.execute(select(func.count(Referral.id)).where(*filters))
    ).scalar_one()
    query = (
        select(Referral)
        .where(*filters)
        .options(selectinload(Referral.patient))
        .order_by(Referral.referral_date.desc(), Referral.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    referrals = result.scalars().all()

    # HIPAA: Log referrals list access
    await log_audit_event(
        db, current_user, "list_referrals", "referral", None, request
    )
    await db.commit()

    page_count = len(referrals)
    return {
        "referrals": [_referral_to_dict(r) for r in referrals],
        "count": page_count,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + page_count if offset + page_count < total else None,
    }


@router.get("/{referral_id}")
async def get_referral(
    request: Request,
    referral_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get referral by ID
    """
    result = await db.execute(
        select(Referral)
        .where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
        # _referral_to_dict reads referral.patient — a lazy load here would
        # raise MissingGreenlet on AsyncSession.
        .options(selectinload(Referral.patient))
    )
    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    # HIPAA: Log referral access
    await log_audit_event(
        db, current_user, "view_referral", "referral", referral.id, request
    )
    await db.commit()

    return _referral_to_dict(referral)


async def _next_referral_number(db: AsyncSession, practice_id: UUID) -> str:
    """Return the next practice-unique referral number for its local day."""
    from app.core.database import row_locks_supported

    is_postgres = row_locks_supported()
    practice_tz = await get_practice_timezone(db, practice_id)
    today = business_date(practice_tz)
    start_utc, end_utc = day_bounds_utc(practice_tz, today)

    if is_postgres:
        day_key = int(today.strftime("%Y%m%d"))
        practice_int = int.from_bytes(
            practice_id.bytes[:8], byteorder="big", signed=False
        ) & 0x7FFFFFFFFFFFFFFF
        lock_key = (practice_int ^ day_key) & 0x7FFFFFFFFFFFFFFF
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    day_prefix = today.strftime("%Y%m%d")
    count_q = select(func.count(Referral.id)).where(
        Referral.practice_id == practice_id,
        Referral.referral_date >= start_utc,
        Referral.referral_date < end_utc,
    )
    count = (await db.execute(count_q)).scalar() or 0
    seq = count + 1
    while seq < count + 10000:
        candidate = f"REF-{day_prefix}-{seq:04d}"
        exists = await db.execute(
            select(Referral.id).where(
                Referral.practice_id == practice_id,
                Referral.referral_number == candidate,
            )
        )
        if exists.scalar_one_or_none() is None:
            return candidate
        seq += 1
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate a referral number",
    )


@router.post("/")
async def create_referral(
    referral_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Create new referral
    """
    # Verify patient exists
    patient_id = referral_data.get("patient_id")
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

    # Generate unique referral number with advisory lock
    referral_number = await _next_referral_number(db, current_user.practice_id)

    # H4 FIX: allowlist client fields; identity/numbering columns are
    # server-set. referral_type is required (nullable=False column).
    fields = {k: v for k, v in referral_data.items() if k in _REFERRAL_WRITABLE_FIELDS}
    fields["referral_type"] = _coerce_enum(ReferralType, fields.get("referral_type"))
    if fields["referral_type"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="referral_type is required",
        )
    fields["status"] = _coerce_enum(ReferralStatus, fields.get("status", ReferralStatus.PENDING))
    # M-09: a new referral starts PENDING or SENT; it cannot be created already
    # completed or cancelled.
    if fields["status"] not in (ReferralStatus.PENDING, ReferralStatus.SENT):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A new referral must be created with status 'pending' or 'sent'",
        )
    if not fields.get("reason"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reason is required",
        )

    await _validate_referral_references(db, current_user, fields)

    referral = Referral(
        practice_id=current_user.practice_id,
        patient_id=patient.id,
        referring_provider_id=current_user.id,
        referral_number=referral_number,
        **fields
    )
    db.add(referral)
    await db.commit()
    await db.refresh(referral)
    referral.patient = patient

    return _referral_to_dict(referral)


@router.put("/{referral_id}")
async def update_referral(
    referral_id: uuid.UUID,
    referral_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Update referral
    """
    result = await db.execute(
        select(Referral)
        .where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
        .options(selectinload(Referral.patient))
    )
    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    # H4 FIX: allowlist update fields; identity/lifecycle columns (id,
    # practice_id, patient_id, referring_provider_id, referral_number,
    # is_deleted, deleted_at, created_at, updated_at) are never
    # client-writable.
    # M-09 FIX: validate referenced ids and the status transition before
    # applying anything.
    incoming = {
        field: referral_data[field]
        for field in _REFERRAL_WRITABLE_FIELDS
        if field in referral_data
    }
    await _validate_referral_references(db, current_user, incoming)

    if "status" in incoming:
        new_status = _coerce_enum(ReferralStatus, incoming["status"])
        if new_status is not None and new_status != referral.status:
            allowed = _REFERRAL_TRANSITIONS.get(referral.status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot change referral status from "
                        f"{getattr(referral.status, 'value', referral.status)} to "
                        f"{getattr(new_status, 'value', new_status)}"
                    ),
                )

    for field in _REFERRAL_WRITABLE_FIELDS:
        if field not in referral_data:
            continue
        value = referral_data[field]
        if field == "referral_type":
            value = _coerce_enum(ReferralType, value)
        elif field == "status":
            value = _coerce_enum(ReferralStatus, value)
        setattr(referral, field, value)

    # Update completed date if status changed to completed
    if referral.status == ReferralStatus.COMPLETED and not referral.completed_date:
        referral.completed_date = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(referral)
    if referral.patient_id:
        p_res = await db.execute(select(Patient).where(Patient.id == referral.patient_id))
        referral.patient = p_res.scalar_one_or_none()

    return _referral_to_dict(referral)


@router.delete("/{referral_id}")
async def delete_referral(
    referral_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete referral
    """
    result = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
    )
    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    # HIPAA Hardening: Soft-delete only to preserve audit trail
    referral.is_deleted = True
    referral.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Referral deleted successfully"}


# Referral Communication Endpoints

@router.get("/{referral_id}/communications")
async def list_referral_communications(
    referral_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List communications for a referral
    """
    # Verify referral exists
    result = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
    )
    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    query = select(ReferralCommunication).where(
        ReferralCommunication.referral_id == referral_id
    ).order_by(ReferralCommunication.created_at.desc())

    result = await db.execute(query)
    communications = result.scalars().all()

    return {"communications": [_communication_to_dict(c) for c in communications], "count": len(communications)}


@router.post("/{referral_id}/communications")
async def add_referral_communication(
    referral_id: uuid.UUID,
    comm_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Add communication to referral
    """
    # Verify referral exists
    result = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
    )
    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    # H4 FIX: allowlist communication fields; referral_id/user_id are
    # server-set (previously a body containing referral_id/user_id crashed
    # with duplicate kwargs).
    fields = {k: v for k, v in comm_data.items() if k in _COMMUNICATION_WRITABLE_FIELDS}
    if not fields.get("communication_type"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="communication_type is required",
        )

    communication = ReferralCommunication(
        referral_id=referral.id,
        user_id=current_user.id,
        **fields
    )
    db.add(communication)
    await db.commit()
    await db.refresh(communication)

    return _communication_to_dict(communication)


# Referral Reports Endpoints

@router.get("/reports/summary")
async def get_referral_summary(
    request: Request,
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get referral summary statistics for a bounded local time range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        instant_range = resolve_instant_range(practice_tz, start_date, end_date)
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Calculate stats via SQL aggregates.
    stats_stmt = select(
        func.count(Referral.id).label('total'),
        func.sum(case((Referral.status == ReferralStatus.COMPLETED, 1), else_=0)).label('completed'),
        func.sum(case((Referral.status == ReferralStatus.PENDING, 1), else_=0)).label('pending'),
        func.sum(case((Referral.status == ReferralStatus.CANCELLED, 1), else_=0)).label('cancelled'),
        func.sum(case((Referral.status == ReferralStatus.NO_SHOW, 1), else_=0)).label('no_shows'),
        func.sum(Referral.referral_fee).label('total_fees'),
        func.sum(case((Referral.referral_received.is_(True), Referral.referral_fee), else_=0)).label('collected_fees')
    ).where(
        Referral.practice_id == current_user.practice_id,
        Referral.is_deleted.is_(False),
        Referral.referral_date >= instant_range.start_utc,
        Referral.referral_date < instant_range.end_utc,
    )
    res = await db.execute(stats_stmt)
    stats = res.one()

    total = stats.total or 0
    completed = stats.completed or 0
    total_fees = float(stats.total_fees or 0)
    collected_fees = float(stats.collected_fees or 0)

    # HIPAA: Log referral summary access
    await log_audit_event(
        db, current_user, "view_referral_summary", "referral_report", None, request
    )
    await db.commit()

    return {
        "total_referrals": total,
        "completed": completed,
        "pending": stats.pending or 0,
        "cancelled": stats.cancelled or 0,
        "no_shows": stats.no_shows or 0,
        "completion_rate": round(completed / total * 100, 2) if total > 0 else 0,
        "total_fees": total_fees,
        "collected_fees": collected_fees,
    }


# Email to Referral Endpoint
class ReferralEmailRequest(BaseModel):
    """Message content for a server-addressed internal referral email."""

    subject: str
    message: str


@router.post("/{referral_id}/email")
async def send_referral_email(
    referral_id: uuid.UUID,
    email_data: ReferralEmailRequest,
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)
    ),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Send PHI only to a verified user at the referral's target practice."""
    result = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.practice_id == current_user.practice_id,
            Referral.is_deleted.is_(False),
        )
    )
    referral = result.scalar_one_or_none()
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found",
        )

    # External specialist addresses are not verified identities. Until a
    # secure referral portal exists, fail closed rather than sending PHI to a
    # caller-selected or directory-only email address.
    if not referral.is_internal or not referral.target_practice_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="External referrals require secure portal delivery; PHI email is disabled",
        )

    recipient_result = await db.execute(
        select(User)
        .where(
            User.practice_id == referral.target_practice_id,
            User.is_active.is_(True),
            User.is_email_verified.is_(True),
            User.role.in_([UserRole.OWNER, UserRole.ADMIN]),
        )
        .order_by(User.role, User.created_at)
        .limit(1)
    )
    recipient = recipient_result.scalar_one_or_none()
    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The target practice has no verified referral recipient",
        )

    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == referral.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = patient_result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    from app.models.practice import Practice
    practice_result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    practice = practice_result.scalar_one_or_none()

    from html import escape as _html_escape

    safe_subject = email_data.subject.replace("\r", " ").replace("\n", " ").strip()
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Referral Communication</h2>
            <p><strong>From:</strong> {_html_escape(practice.name if practice else 'CoreDent Practice')}</p>
            <p><strong>Re:</strong> Patient Referral - {_html_escape(patient.first_name or '')} {_html_escape(patient.last_name or '')}</p>
            <hr>
            <div style="margin: 20px 0;">
                {_html_escape(email_data.message).replace(chr(10), '<br>')}
            </div>
            <hr>
            <p><strong>Referral Number:</strong> {_html_escape(referral.referral_number or '')}</p>
            <p><strong>Referral Type:</strong> {_html_escape(referral.referral_type.value if hasattr(referral.referral_type, 'value') else str(referral.referral_type))}</p>
            <p><strong>Date:</strong> {referral.referral_date.strftime('%Y-%m-%d') if referral.referral_date else 'N/A'}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                This message contains confidential health information intended only for the verified recipient.
            </p>
        </body>
    </html>
    """

    try:
        await email_service.send_email(
            to=recipient.email,
            subject=safe_subject,
            html_content=html_content,
        )
    except (ValueError, TypeError, ConnectionError) as exc:
        from app.core.email import log_email_failure

        log_email_failure(exc, "referral_email", recipient.email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Referral email could not be delivered",
        ) from exc

    communication = ReferralCommunication(
        referral_id=referral.id,
        user_id=current_user.id,
        communication_type="email",
        direction="outgoing",
        subject=safe_subject,
        content=email_data.message,
    )
    db.add(communication)
    await db.commit()
    return {"message": "Email sent successfully"}