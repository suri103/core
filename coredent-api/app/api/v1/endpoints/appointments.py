"""
Appointment Endpoints
CRUD operations for appointments
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_, select, text
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid as uuid_lib
import asyncio
import hashlib
import logging

from app.core.business_time import (
    DateRangeError,
    business_date,
    day_bounds_utc,
    ensure_utc,
    get_practice_timezone,
    resolve_instant_range,
)

from app.core.database import get_db, row_locks_supported
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.models.appointment import Appointment, AppointmentStatus, Chair
from app.models.patient import Patient
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentListResponse,
    AppointmentSlot,
    AppointmentStatusUpdate,
    AppointmentCancelRequest,
    AppointmentRescheduleRequest,
)

logger = logging.getLogger(__name__)

# H10 FIX: appointment lifecycle transitions. COMPLETED / CANCELLED are
# terminal — a cancelled slot must not be resurrected without re-running
# the conflict check, and completed visits must not regress.
_APPOINTMENT_TRANSITIONS = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CHECKED_IN: {
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.IN_PROGRESS: {
        AppointmentStatus.COMPLETED,
    },
    AppointmentStatus.NO_SHOW: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
}

# A new appointment may only start in a pre-visit state; clients cannot
# mint COMPLETED/CANCELLED/NO_SHOW records directly.
_CREATABLE_STATUSES = {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}


def _validate_appointment_transition(current: AppointmentStatus, new: AppointmentStatus) -> None:
    if new == current:
        return
    allowed = _APPOINTMENT_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change appointment status from {current.value} to {new.value}",
        )


_TERMINAL_APPOINTMENT_STATUSES = {
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
}


def _ensure_appointment_mutable(appointment: Appointment) -> None:
    """Reject edits that would mutate a terminal appointment record.

    Completed visits are part of the clinical and billing history; cancelled
    appointments are the audit trail for a released slot. Neither may be
    silently rescheduled, edited, or cancelled again through a different
    mutation route.
    """
    if appointment.status in _TERMINAL_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot modify an appointment in terminal status "
                f"{appointment.status.value}"
            ),
        )


async def _acquire_booking_lock(db, practice_id, *specs) -> None:
    """
    C4 FIX (fine-grained): serialize booking writes on the *conflict
    dimensions* instead of practice-wide.

    Two appointments conflict (see ``_build_conflict_query``) when they share
    the same PATIENT, the same PROVIDER, or the same CHAIR. Each ``specs``
    entry is a ``(tag, value)`` pair identifying one such dimension; every
    entry takes one transaction-scoped Postgres advisory lock keyed on
    ``hash(tag, practice_id, value)``. Any two requests that could produce
    conflicting appointments therefore share at least one lock and serialize,
    while requests for disjoint patients/providers/chairs no longer queue
    behind each other (the old behavior: one practice-wide lock).

    ``value=None`` entries are skipped (no resource, nothing to serialize
    on). Called with no specs at all, it falls back to the legacy
    practice-wide lock so an un-migrated call site can never silently skip
    serialization.
    """
    from app.core.database import row_locks_supported
    if not row_locks_supported():
        return
    if not specs:
        specs = (("practice", practice_id),)
    lock_keys = set()
    for tag, value in specs:
        if value is None:
            continue
        digest = hashlib.blake2b(
            f"{tag}|{practice_id}|{value}".encode("utf-8"), digest_size=8
        ).digest()
        lock_keys.add(int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF)

    # Sort keys globally to prevent advisory-lock deadlocks under concurrent bookings
    for k in sorted(lock_keys):
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": k})


def _build_conflict_query(
    practice_id,
    patient_id,
    start_time: datetime,
    end_time: datetime,
    provider_id=None,
    chair_id=None,
    exclude_id=None,
):
    """
    H7 FIX: OR semantics — an overlap conflicts when it involves the SAME
    PATIENT, the SAME PROVIDER (in any chair), or the SAME CHAIR (with any
    provider). The old query ANDed the provider and chair filters, so a
    provider double-booked into a different chair passed validation, while
    an appointment with neither resource set spurious-409'd against
    anything overlapping practice-wide.
    """
    q = select(Appointment.id).where(
        Appointment.practice_id == practice_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status != AppointmentStatus.CANCELLED,
    )
    if exclude_id is not None:
        q = q.where(Appointment.id != exclude_id)

    conflict_clauses = [Appointment.patient_id == patient_id]
    if provider_id:
        conflict_clauses.append(Appointment.provider_id == provider_id)
    if chair_id:
        conflict_clauses.append(Appointment.chair_id == chair_id)
    return q.where(or_(*conflict_clauses))


router = APIRouter()


async def _execute(db: Union[AsyncSession, Session], query):
    """Execute a SQLAlchemy query on either async or sync session."""
    result = db.execute(query)
    if asyncio.iscoroutine(result):
        result = await result
    return result


def _display_name(entity) -> str:
    """Best-effort display name from user/patient objects."""
    if entity is None:
        return ""
    first = getattr(entity, "first_name", None) or ""
    last = getattr(entity, "last_name", None) or ""
    return f"{first} {last}".strip()


def _serialize_appointment(
    appointment: Appointment,
    provider_name: Optional[str] = None,
    patient_name: Optional[str] = None,
) -> AppointmentResponse:
    """Map an ORM Appointment to AppointmentResponse plus the read-model aliases.

    Only already-loaded relationship attributes are used (guarded via `__dict__`)
    so async lazy-loads are never triggered during response serialization.
    """
    loaded = getattr(appointment, "__dict__", {})
    patient = loaded.get("patient") or None
    provider = loaded.get("provider") or None
    chair = loaded.get("chair") or None
    return AppointmentResponse(
        id=appointment.id,
        practice_id=appointment.practice_id,
        patient_id=appointment.patient_id,
        provider_id=appointment.provider_id,
        chair_id=appointment.chair_id,
        appointment_type=appointment.appointment_type,
        status=appointment.status,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        duration=appointment.duration,
        notes=appointment.notes,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
        type=appointment.appointment_type.value if appointment.appointment_type else None,
        patient_name=patient_name if patient_name is not None else _display_name(patient),
        provider_name=provider_name if provider_name is not None else _display_name(provider),
        operatory_id=chair.id if chair else None,
        operatory_name=chair.name if chair else None,
    )


@router.get("/", response_model=AppointmentListResponse)
async def list_appointments(
    start_date: Optional[datetime] = Query(None, description="UTC start timestamp for filtering"),
    end_date: Optional[datetime] = Query(None, description="UTC end timestamp (exclusive) for filtering"),
    status: Optional[AppointmentStatus] = Query(None, description="Filter by status"),
    provider_id: Optional[str] = Query(None, description="Filter by provider"),
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentListResponse:
    """List appointments using bounded UTC instants for one practice.

    Omitted dates use a rolling 90-day interactive window centred on the
    present (30 days of history and 60 days ahead). Explicit datetimes retain
    instant semantics after UTC normalization and may span at most 366 days.
    """
    tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        window = resolve_instant_range(
            tz,
            start_date,
            end_date,
            moment=datetime.now(timezone.utc) + timedelta(days=60),
        )
    except DateRangeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    filters = [
        Appointment.practice_id == current_user.practice_id,
        Appointment.start_time >= window.start_utc,
        Appointment.start_time < window.end_utc,
    ]
    if status:
        filters.append(Appointment.status == status)
    if provider_id:
        filters.append(Appointment.provider_id == provider_id)
    if patient_id:
        filters.append(Appointment.patient_id == patient_id)

    query = (
        select(Appointment)
        .where(*filters)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.provider),
            selectinload(Appointment.chair),
        )
        .order_by(Appointment.start_time, Appointment.id)
        .limit(limit)
        .offset(offset)
    )
    result = await _execute(db, query)
    appointments = result.scalars().all()
    total = (await _execute(db, select(func.count(Appointment.id)).where(*filters))).scalar_one()

    await log_audit_event(
        db, current_user, "list_appointments", "appointment", None, request
    )
    await db.commit()

    next_offset = offset + len(appointments) if offset + len(appointments) < total else None
    return AppointmentListResponse(
        appointments=[_serialize_appointment(a) for a in appointments],
        count=len(appointments),
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


@router.get("/stats", response_model=dict)
async def get_appointment_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get today’s appointment statistics in the practice’s local calendar."""
    tz = await get_practice_timezone(db, current_user.practice_id)
    local_today = business_date(tz)
    today_start, today_end = day_bounds_utc(tz, local_today)

    today_query = select(Appointment).where(
        Appointment.practice_id == current_user.practice_id,
        Appointment.start_time >= today_start,
        Appointment.start_time < today_end,
    )
    today_result = await db.execute(today_query)
    today_appointments = today_result.scalars().all()

    confirmed = sum(1 for apt in today_appointments if apt.status == AppointmentStatus.CONFIRMED)
    pending = sum(1 for apt in today_appointments if apt.status == AppointmentStatus.SCHEDULED)
    cancelled = sum(1 for apt in today_appointments if apt.status == AppointmentStatus.CANCELLED)
    completed = sum(1 for apt in today_appointments if apt.status == AppointmentStatus.COMPLETED)

    return {
        "todayAppointments": len(today_appointments),
        "confirmed": confirmed,
        "pending": pending,
        "cancelled": cancelled,
        "completed": completed,
    }


@router.get("/types", response_model=dict)
async def get_appointment_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get available appointment types
    """
    # Return standard dental appointment types
    types = [
        {"id": "checkup", "name": "Checkup", "duration": 30, "description": "Routine dental examination"},
        {"id": "cleaning", "name": "Cleaning", "duration": 60, "description": "Professional teeth cleaning"},
        {"id": "filling", "name": "Filling", "duration": 45, "description": "Dental filling procedure"},
        {"id": "crown", "name": "Crown", "duration": 60, "description": "Crown placement"},
        {"id": "extraction", "name": "Extraction", "duration": 45, "description": "Tooth extraction"},
        {"id": "root_canal", "name": "Root Canal", "duration": 90, "description": "Root canal treatment"},
        {"id": "whitening", "name": "Whitening", "duration": 60, "description": "Teeth whitening"},
        {"id": "consultation", "name": "Consultation", "duration": 30, "description": "Initial consultation"},
        {"id": "follow_up", "name": "Follow-up", "duration": 30, "description": "Follow-up appointment"},
        {"id": "emergency", "name": "Emergency", "duration": 30, "description": "Emergency dental visit"},
    ]
    return {"types": types}


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid_lib.UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """
    Get appointment by ID
    """
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.provider),
            selectinload(Appointment.chair),
        )
        .where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # HIPAA: Log appointment access
    await log_audit_event(
        db, current_user, "view_appointment", "appointment", appointment.id, request
    )
    await db.commit()

    return _serialize_appointment(appointment)


@router.post("/", response_model=AppointmentResponse)
async def create_appointment(
    appointment_data: AppointmentCreate,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> AppointmentResponse:
    """
    Create new appointment
    """
    # Verify patient exists and belongs to practice
    result = await _execute(
        db,
        select(Patient).where(
            Patient.id == appointment_data.patient_id,
            Patient.practice_id == current_user.practice_id,
        ),
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # M15 FIX: soft-deleted patients must not be bookable.
    from app.models.patient import PatientStatus
    if patient.status == PatientStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient is inactive and cannot be scheduled",
        )

    # Expert Hardening: Verify chair belongs to practice
    if appointment_data.chair_id:
        chair_check = await db.execute(
            select(Chair).where(
                Chair.id == appointment_data.chair_id,
                Chair.practice_id == current_user.practice_id
            )
        )
        if not chair_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chair selection for your practice"
            )

    # Expert Hardening: Verify provider belongs to practice
    if appointment_data.provider_id:
        provider_check = await db.execute(
            select(User).where(
                User.id == appointment_data.provider_id,
                User.practice_id == current_user.practice_id
            )
        )
        if not provider_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider selection for your practice"
            )

    # H10 FIX: new appointments may only start in a pre-visit state.
    initial_status = appointment_data.status or AppointmentStatus.SCHEDULED
    if initial_status not in _CREATABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New appointments cannot be created with status {initial_status.value}",
        )

    # C4 FIX: serialize booking writes on their conflict dimensions, then
    # re-check conflicts under the lock so two concurrent requests cannot
    # both observe zero conflicts and double-book the same slot. Disjoint
    # patient/provider/chair combinations no longer serialize against each
    # other (they cannot conflict, per _build_conflict_query's OR semantics).
    await _acquire_booking_lock(
        db,
        current_user.practice_id,
        ("patient", appointment_data.patient_id),
        ("provider", appointment_data.provider_id),
        ("chair", appointment_data.chair_id),
    )

    # Check for scheduling conflicts (H7: same patient OR provider OR chair)
    conflict_query = _build_conflict_query(
        practice_id=current_user.practice_id,
        patient_id=appointment_data.patient_id,
        start_time=appointment_data.start_time,
        end_time=appointment_data.end_time,
        provider_id=appointment_data.provider_id,
        chair_id=appointment_data.chair_id,
    )
    conflicts = (await _execute(db, conflict_query)).scalars().all()

    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scheduling conflict detected",
        )

    # Create appointment
    appointment = Appointment(
        practice_id=current_user.practice_id,
        patient_id=appointment_data.patient_id,
        provider_id=appointment_data.provider_id,
        chair_id=appointment_data.chair_id,
        appointment_type=appointment_data.appointment_type,
        status=initial_status,
        start_time=appointment_data.start_time,
        end_time=appointment_data.end_time,
        duration=appointment_data.duration,
        notes=appointment_data.notes,
    )

    db.add(appointment)
    await db.flush()

    # L18 FIX: appointment mutations are part of the HIPAA audit trail
    # (reads were logged; writes were not). Single commit ensures atomic trail (M11).
    await log_audit_event(
        db, current_user, "appointment_created", "appointment", appointment.id, request
    )
    await db.commit()

    # Re-fetch with relationships loaded so the read-model aliases
    # (patient_name / provider_name / operatory_id / operatory_name) are fresh.
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.provider),
            selectinload(Appointment.chair),
        )
        .where(Appointment.id == appointment.id)
    )
    appointment = result.scalar_one()

    return _serialize_appointment(appointment)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid_lib.UUID,
    appointment_data: AppointmentUpdate,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> AppointmentResponse:
    """
    Update appointment
    """
    appointment_stmt = select(Appointment).where(
        Appointment.id == appointment_id,
        Appointment.practice_id == current_user.practice_id,
    )
    if row_locks_supported():
        appointment_stmt = appointment_stmt.with_for_update()
    result = await db.execute(appointment_stmt)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    update_data = appointment_data.model_dump(exclude_unset=True)

    # H-07: terminal appointments cannot be edited through the generic
    # update route, even when the caller omits ``status``.
    if update_data:
        _ensure_appointment_mutable(appointment)

    # H10 FIX: validate the status transition (terminal states are locked).
    if "status" in update_data and update_data["status"] is not None:
        _validate_appointment_transition(appointment.status, update_data["status"])

    # H8 FIX: tenant-validate reassigned resources. The create path checks
    # these; the update path used to apply them blindly, letting a caller
    # point an appointment at another clinic's chair/provider (FKs are
    # global) and then serialize the other tenant's chair name.
    if "chair_id" in update_data and update_data["chair_id"] is not None:
        chair_check = await db.execute(
            select(Chair).where(
                Chair.id == update_data["chair_id"],
                Chair.practice_id == current_user.practice_id,
            )
        )
        if not chair_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chair selection for your practice",
            )
    if "provider_id" in update_data and update_data["provider_id"] is not None:
        provider_check = await db.execute(
            select(User).where(
                User.id == update_data["provider_id"],
                User.practice_id == current_user.practice_id,
            )
        )
        if not provider_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider selection for your practice",
            )

    # H8 FIX: the conflict check runs whenever time OR provider OR chair
    # changes — reassigning just a provider used to bypass it entirely.
    scheduling_fields = {"start_time", "end_time", "provider_id", "chair_id"}
    if scheduling_fields & set(update_data):
        start_time = update_data.get("start_time") or appointment.start_time
        end_time = update_data.get("end_time") or appointment.end_time
        provider_id = update_data.get("provider_id", appointment.provider_id)
        chair_id = update_data.get("chair_id", appointment.chair_id)

        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time",
            )

        # Hold locks on BOTH the old and the new resource values: a concurrent
        # creator targeting the provider/chair being vacated must serialize
        # against this move just as much as one targeting the destination.
        await _acquire_booking_lock(
            db,
            current_user.practice_id,
            ("patient", appointment.patient_id),
            ("provider", appointment.provider_id),
            ("provider", provider_id),
            ("chair", appointment.chair_id),
            ("chair", chair_id),
        )

        # M1 FIX: Refresh row under the booking lock to ensure status has not
        # moved concurrently to COMPLETED/CANCELLED before checking conflicts.
        await db.refresh(appointment)
        if update_data:
            _ensure_appointment_mutable(appointment)

        conflict_query = _build_conflict_query(
            practice_id=current_user.practice_id,
            patient_id=appointment.patient_id,
            start_time=start_time,
            end_time=end_time,
            provider_id=provider_id,
            chair_id=chair_id,
            exclude_id=appointment_id,
        )
        conflicts = (await db.execute(conflict_query)).scalars().all()
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Scheduling conflict detected",
            )

        # M17 FIX: keep duration consistent with the (possibly new) times —
        # reschedule derives end_time from duration, so a stale value
        # permanently shifted rescheduled appointments.
        if "start_time" in update_data or "end_time" in update_data:
            update_data["duration"] = int((end_time - start_time).total_seconds() // 60)

    for field, value in update_data.items():
        setattr(appointment, field, value)

    # L18 FIX: HIPAA audit trail for appointment writes (atomic single commit, M11).
    await log_audit_event(
        db, current_user, "appointment_updated", "appointment", appointment.id, request
    )
    await db.commit()

    # Re-fetch with relationships loaded so the read-model aliases are fresh.
    # F-T4 FIX: keep the practice_id predicate on every read (same row by PK,
    # but the invariant must hold on every query).
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.provider),
            selectinload(Appointment.chair),
        )
        .where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one()

    return _serialize_appointment(appointment)


@router.delete("/{appointment_id}", response_model=dict)
async def delete_appointment(
    appointment_id: uuid_lib.UUID,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete appointment (soft delete by cancelling)
    """
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Soft delete by cancelling. A completed or already-cancelled record is
    # terminal and must remain unchanged.
    _ensure_appointment_mutable(appointment)
    _validate_appointment_transition(appointment.status, AppointmentStatus.CANCELLED)
    appointment.status = AppointmentStatus.CANCELLED
    await db.commit()

    # L18 FIX: deletes/cancellations must be in the audit trail.
    await log_audit_event(
        db, current_user, "appointment_deleted", "appointment", appointment.id, request
    )
    await db.commit()

    return {"message": "Appointment cancelled successfully"}


@router.put("/{appointment_id}/status", response_model=dict)
async def update_appointment_status(
    appointment_id: uuid_lib.UUID,
    payload: AppointmentStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update an appointment's status from the scheduling UI."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    # H10 FIX: validate the lifecycle transition (e.g. COMPLETED cannot
    # regress to SCHEDULED; CANCELLED is terminal).
    _validate_appointment_transition(appointment.status, payload.status)

    appointment.status = payload.status
    await log_audit_event(
        db, current_user, "appointment_status_updated", "appointment", appointment.id, request
    )
    await db.commit()
    return {
        "message": "Appointment status updated",
        "id": str(appointment.id),
        "status": payload.status.value,
    }


@router.post("/{appointment_id}/cancel", response_model=dict)
async def cancel_appointment(
    appointment_id: uuid_lib.UUID,
    request: Request,
    payload: AppointmentCancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Cancel an appointment (soft) and record an optional reason."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    _validate_appointment_transition(appointment.status, AppointmentStatus.CANCELLED)
    _ensure_appointment_mutable(appointment)
    appointment.status = AppointmentStatus.CANCELLED
    # M-6 FIX: persist the cancellation reason in its own column instead
    # of appending it to clinical notes. The ``notes`` field is for
    # clinical observations; mixing state-machine metadata into it
    # made both downstream filtering and HIPAA audit review harder.
    if payload.reason:
        appointment.cancellation_reason = payload.reason
    await log_audit_event(
        db, current_user, "appointment_cancelled", "appointment", appointment.id, request
    )
    await db.commit()
    return {"message": "Appointment cancelled successfully", "id": str(appointment.id)}


@router.put("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: uuid_lib.UUID,
    payload: AppointmentRescheduleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> AppointmentResponse:
    """Reschedule an appointment to a new chair/start time (recomputes end_time)."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    # H-07: rescheduling is a mutation too; it must not reopen or rewrite a
    # completed/cancelled clinical record.
    _ensure_appointment_mutable(appointment)

    new_chair_id = appointment.chair_id
    if payload.chair_id is not None:
        chair_result = await db.execute(
            select(Chair).where(
                Chair.id == payload.chair_id,
                Chair.practice_id == current_user.practice_id,
            )
        )
        if not chair_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chair selection for your practice",
            )
        new_chair_id = payload.chair_id

    new_start = payload.start_time or appointment.start_time
    new_end = new_start + timedelta(minutes=appointment.duration)
    if payload.chair_id is not None or payload.start_time is not None:
        # Reassigning a chair changes the scheduling resource just as much as
        # moving the start time. Hold the same lock and check the effective
        # state before persisting either value.
        # Same old+new reasoning as the generic update path: the chair being
        # vacated and the chair being claimed are both conflict dimensions.
        await _acquire_booking_lock(
            db,
            current_user.practice_id,
            ("patient", appointment.patient_id),
            ("provider", appointment.provider_id),
            ("chair", appointment.chair_id),
            ("chair", new_chair_id),
        )
        conflict_query = _build_conflict_query(
            practice_id=current_user.practice_id,
            patient_id=appointment.patient_id,
            start_time=new_start,
            end_time=new_end,
            provider_id=appointment.provider_id,
            chair_id=new_chair_id,
            exclude_id=appointment_id,
        )
        conflicts = (await db.execute(conflict_query)).scalars().all()
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Scheduling conflict detected",
            )

    if payload.chair_id is not None:
        appointment.chair_id = new_chair_id
    if payload.start_time is not None:
        appointment.start_time = new_start
        appointment.end_time = new_end

    await db.commit()

    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.provider),
            selectinload(Appointment.chair),
        )
        .where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one()

    await log_audit_event(
        db, current_user, "appointment_rescheduled", "appointment", appointment.id, request
    )
    await db.commit()

    return _serialize_appointment(appointment)


@router.get("/slots/available", response_model=List[AppointmentSlot])
async def get_available_slots(
    date: datetime = Query(..., description="Date to check availability"),
    duration: int = Query(30, description="Appointment duration in minutes"),
    provider_id: Optional[str] = Query(None, description="Filter by provider"),
    chair_id: Optional[str] = Query(None, description="Filter by chair"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AppointmentSlot]:
    """
    Get available appointment slots
    """
    # Define business hours (9 AM to 5 PM) in the practice's own timezone.
    start_hour = 9
    end_hour = 17

    # A naive value from a date-picker is a practice-local calendar value;
    # an aware value remains its supplied UTC instant. This avoids silently
    # shifting a local YYYY-MM-DD selection through the server timezone.
    tz = await get_practice_timezone(db, current_user.practice_id)
    local_date = (
        date.replace(tzinfo=tz)
        if date.tzinfo is None
        else ensure_utc(date).astimezone(tz)
    )
    day_start, day_end = day_bounds_utc(tz, local_date.date())

    # PERFORMANCE OPTIMIZATION: Fetch all appointments for the day in a single query
    # instead of querying inside the loop.
    query = select(Appointment).where(
        Appointment.practice_id == current_user.practice_id,
        Appointment.start_time >= day_start,
        Appointment.start_time < day_end,
        Appointment.status != AppointmentStatus.CANCELLED,
    )

    if provider_id:
        query = query.where(Appointment.provider_id == provider_id)
    if chair_id:
        query = query.where(Appointment.chair_id == chair_id)

    result = await db.execute(query)
    day_appointments = result.scalars().all()

    # Generate slots for the day in the practice's local time.
    slots = []
    current_time = local_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    business_end_time = local_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

    while current_time + timedelta(minutes=duration) <= business_end_time:
        slot_end = current_time + timedelta(minutes=duration)

        # Check if slot is available (in-memory overlap check)
        is_available = True
        for apt in day_appointments:
            # M21 FIX: normalize DB datetimes to aware UTC (SQLite returns
            # naive values; comparing them with the aware local slot times
            # raised TypeError on every call once a same-day appointment
            # existed).
            apt_start = ensure_utc(apt.start_time)
            apt_end = ensure_utc(apt.end_time)
            if current_time < apt_end and slot_end > apt_start:
                is_available = False
                break

        if is_available:
            slots.append(AppointmentSlot(
                start_time=current_time,
                end_time=slot_end,
                duration=duration,
                is_available=True,
            ))

        current_time += timedelta(minutes=15)  # 15 minute intervals

    return slots


@router.post("/{appointment_id}/reminder", response_model=dict)
async def send_appointment_reminder(
    appointment_id: uuid_lib.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Send an appointment reminder to the patient (email, durable queue).

    Previously this endpoint only returned a success message without sending
    anything. It now enqueues a real reminder email to the patient's address
    and records an audit event.
    """
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.patient))
        .where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    patient = getattr(appointment, "patient", None)
    patient_email = getattr(patient, "email", "") or ""
    patient_name = (
        f"{patient.first_name} {patient.last_name}".strip()
        if patient is not None
        else ""
    )
    practice_tz = await get_practice_timezone(db, appointment.practice_id)
    appointment_start = ensure_utc(appointment.start_time)
    appt_time = appointment_start.astimezone(practice_tz).strftime(
        "%B %d, %Y at %I:%M %p %Z"
    )

    message = (
        "Appointment has no patient email on file; reminder not sent."
        if not patient_email
        else f"Reminder sent to {patient_email} for appointment on {appt_time}"
    )

    if patient_email:
        from app.models.communication import (
            MessageDirection,
            MessageStatus,
            MessageType,
            PatientMessage,
        )
        from html import escape as _html_escape

        safe_name = _html_escape(patient_name or "there")
        safe_type = _html_escape(
            appointment.appointment_type.value if appointment.appointment_type else "appointment"
        )
        request_key = (request.headers.get("Idempotency-Key") or "").strip()[:200]
        dedupe_key = (
            f"manual-appointment-reminder:{appointment.id}:{request_key}"
            if request_key
            else None
        )
        try:
            delivery = None
            if dedupe_key:
                delivery_result = await db.execute(
                    select(PatientMessage).where(
                        PatientMessage.practice_id == current_user.practice_id,
                        PatientMessage.dedupe_key == dedupe_key,
                    )
                )
                delivery = delivery_result.scalar_one_or_none()

            if delivery is None:
                delivery = PatientMessage(
                    practice_id=current_user.practice_id,
                    patient_id=appointment.patient_id,
                    appointment_id=appointment.id,
                    message_type=MessageType.EMAIL,
                    direction=MessageDirection.OUTBOUND,
                    status=MessageStatus.PENDING,
                    recipient_email=patient_email,
                    subject="Appointment Reminder — CoreDent",
                    content=(
                        f"<p>Dear {safe_name},</p>"
                        f"<p>This is a reminder for your {safe_type} appointment on "
                        f"<strong>{appt_time}</strong>.</p>"
                        f"<p>If you need to reschedule, please contact the office.</p>"
                    ),
                    dedupe_key=dedupe_key,
                    next_attempt_at=datetime.now(timezone.utc),
                )
                db.add(delivery)
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    if not dedupe_key:
                        raise
                    delivery_result = await db.execute(
                        select(PatientMessage).where(
                            PatientMessage.practice_id == current_user.practice_id,
                            PatientMessage.dedupe_key == dedupe_key,
                        )
                    )
                    delivery = delivery_result.scalar_one_or_none()
                    if delivery is None:
                        raise

            from app.core.communication_tasks import send_message_task

            try:
                send_message_task.delay(str(delivery.id))
            except Exception as publish_exc:
                # The committed PENDING row is scanned by Beat, so publication
                # failure is observable but cannot drop the reminder.
                logger.warning(
                    "Appointment reminder %s remains pending for dispatcher recovery: %s",
                    delivery.id,
                    publish_exc,
                )
            message = f"Reminder queued for {patient_email} for appointment on {appt_time}"
        except Exception as e:
            logger.error("Failed to queue appointment reminder for %s: %s", appointment_id, e)
            message = "Reminder could not be queued. Please try again later."

    await log_audit_event(
        db, current_user, "appointment_reminder", "appointment", appointment.id, request
    )
    await db.commit()

    return {"message": message}