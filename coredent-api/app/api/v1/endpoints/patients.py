"""
Patient Endpoints
CRUD operations for patients
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from sqlalchemy.orm import selectinload
from sqlalchemy import select, or_, update, delete
from sqlalchemy.exc import IntegrityError
from uuid import UUID
import uuid
import json
import os
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient, PatientStatus
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, PatientListItem
from app.schemas.common import PaginatedResponse
from app.api.deps import get_current_user, get_current_practice_id, Pagination, verify_csrf, require_role
from app.core.audit import log_audit_event
from app.core.sanitization import sanitize_search_query
from app.core.search_index import hmac_index, update_patient_search_indexes
from app.core.rate_limit import user_rate_limit
from app.core.limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from typing import List, Optional

from app.models.clinical import ClinicalNote
from app.schemas.clinical import ClinicalNoteResponse
from app.api.v1.endpoints.clinical_notes import (
    CLINICAL_ROLES,
    _to_response,
    _get_patient_or_404,
)
from app.schemas.reference import PatientSearchRef
from app.schemas.patient_export import PatientExportResponse
from app.services.plan_quota import enforce_plan_quota
router = APIRouter()


@router.get("", response_model=PaginatedResponse[PatientListItem])
@user_rate_limit("30/minute")  # SECURITY: per-user cap on PHI list endpoint
async def list_patients(
    request: Request,
    query: str = Query(None, description="Search by name, email, or phone"),
    status_filter: str = Query(None, alias="status"),
    pagination: Pagination = Depends(),
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """
    List patients with search and filtering (paginated)
    """
    # HIPAA: Log PHI list access
    await log_audit_event(
        db, current_user, "patient_list_viewed", "patient", None, request
    )
    await db.commit()

    # Build base query.
    # L13 FIX: dropped the selectinload(Patient.appointments) eager load —
    # PatientListItem.last_visit/next_appointment have no backing model
    # attributes (always None), so the join loaded each patient's entire
    # appointment history for zero benefit.
    # M15 FIX: soft-deleted (inactive) patients are hidden unless the
    # caller explicitly filters for them.
    target_status: Optional[PatientStatus] = None
    if status_filter:
        s_clean = status_filter.strip().lower()
        if s_clean in ("active", "patientstatus.active"):
            target_status = PatientStatus.ACTIVE
        elif s_clean in ("inactive", "patientstatus.inactive"):
            target_status = PatientStatus.INACTIVE

    base_stmt = select(Patient).where(Patient.practice_id == practice_id)
    if target_status is not None:
        base_stmt = base_stmt.where(Patient.status == target_status)
    elif not status_filter:
        base_stmt = base_stmt.where(Patient.status != PatientStatus.INACTIVE)

    # Apply search - two-phase approach for encrypted fields:
    # Phase 1: HMAC exact match (fast path, O(1))
    # Phase 2: In-memory prefix/substring fallback on decrypted values
    # when no exact match found and query >= 2 chars (type-ahead UX).
    use_in_memory_fallback = False
    if query:
        query = sanitize_search_query(query)
        if query:
            search_hmac = hmac_index(query)
            filters = []
            if search_hmac:
                filters.append(Patient.search_index_email == search_hmac)
                filters.append(Patient.search_index_phone == search_hmac)
                filters.append(Patient.search_index_last_name == search_hmac)
            # Also try exact match on non-encrypted fields
            filters.append(Patient.first_name == query)
            filters.append(Patient.last_name == query)

            if len(query) >= 2:
                # Phase 1: Try exact HMAC match first
                exact_stmt = base_stmt.where(or_(*filters))
                exact_result = await db.execute(exact_stmt)
                exact_patients = exact_result.scalars().all()

                if not exact_patients:
                    # Phase 2: Load practice patients, filter in-memory
                    # on decrypted values.  Dental practices typically <5k
                    # patients so this is acceptable.
                    use_in_memory_fallback = True
                    # L14 FIX: cap raised from 1000 — with the old cap the
                    # reported `total` silently understated and later pages
                    # became unreachable for larger practices. 5000 covers
                    # the realistic dental-practice range; the totals remain
                    # a lower bound beyond the cap.
                    base_stmt = base_stmt.order_by(Patient.updated_at.desc()).limit(5000)
                else:
                    base_stmt = exact_stmt
            else:
                base_stmt = base_stmt.where(or_(*filters))

    # Apply status filter (target_status already applied to base_stmt above)
    if target_status is not None and not use_in_memory_fallback:
        pass  # already filtered in base_stmt

    # Get total count BEFORE pagination
    from sqlalchemy import func

    if use_in_memory_fallback:
        # In-memory path: load all, filter, then paginate manually.
        all_result = await db.execute(base_stmt)
        all_patients = all_result.scalars().all()
        q_lower = query.lower() if query else ""
        matched = [
            p for p in all_patients
            if q_lower in (p.first_name or "").lower()
            or q_lower in (p.last_name or "").lower()
            or q_lower in (p.email or "").lower()
            or q_lower in (p.phone or "").lower()
            or q_lower in f"{(p.first_name or '').lower()} {(p.last_name or '').lower()}"
        ]
        if target_status is not None:
            matched = [
                p for p in matched
                if p.status == target_status or (hasattr(p.status, 'value') and p.status.value == target_status.value)
            ]
        total = len(matched)
        patients = matched[pagination.offset:pagination.offset + pagination.limit]
    else:
        # SQL path: count + paginate as before.
        count_stmt = select(func.count()).select_from(Patient).where(Patient.practice_id == practice_id)
        if target_status is not None:
            count_stmt = count_stmt.where(Patient.status == target_status)
        elif not status_filter:
            count_stmt = count_stmt.where(Patient.status != PatientStatus.INACTIVE)
        if query and not use_in_memory_fallback:
            query_clean = sanitize_search_query(query)
            if query_clean:
                search_hmac = hmac_index(query_clean)
                count_filters = []
                if search_hmac:
                    count_filters.append(Patient.search_index_email == search_hmac)
                    count_filters.append(Patient.search_index_phone == search_hmac)
                    count_filters.append(Patient.search_index_last_name == search_hmac)
                count_filters.append(Patient.first_name == query_clean)
                count_filters.append(Patient.last_name == query_clean)
                count_stmt = count_stmt.where(or_(*count_filters))

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination to data query
        stmt = base_stmt.offset(pagination.offset).limit(pagination.limit)

        # Execute query
        result = await db.execute(stmt)
        patients = result.scalars().all()

    # Return paginated response
    return PaginatedResponse.create(
        items=patients,
        total=total,
        page=pagination.page,
        limit=pagination.limit
    )


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    request: Request,
    patient_in: PatientCreate,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
    _quota: None = Depends(enforce_plan_quota("patients")),
    _csrf: bool = Depends(verify_csrf),  # SECURITY FIX: CSRF protection
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """
    Create new patient (includes integrity check for duplicates)

    QUOTA: ``enforce_plan_quota("patients")`` rejects creation once the
    practice's active plan has hit its ``limits.patients`` ceiling.
    """
    # Expert Integrity: Check for duplicate patient in the same practice
    # Use HMAC index columns since email/phone are encrypted at rest
    email_hmac = hmac_index(patient_in.email)
    phone_hmac = hmac_index(patient_in.phone)
    dup_filters = []
    if email_hmac:
        dup_filters.append(Patient.search_index_email == email_hmac)
    if phone_hmac:
        dup_filters.append(Patient.search_index_phone == phone_hmac)
    if dup_filters:
        duplicate_query = select(Patient).where(
            Patient.practice_id == practice_id,
            # B8 policy alignment: match the partial unique index predicate —
            # uniqueness is enforced among non-inactive rows only, so an
            # inactive historical record must not block re-use of a contact.
            Patient.status.isnot(None),
            Patient.status != PatientStatus.INACTIVE,
            or_(*dup_filters)
        )
        result = await db.execute(duplicate_query)
        # M16 FIX: .first() — scalar_one_or_none() raised
        # MultipleResultsFound (unhandled 500) on every create once a
        # duplicate pair existed.
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A patient with this email or phone already exists in this practice. Please verify the record."
            )

    # Create patient
    data = patient_in.model_dump()
    # Pop the search-index fields if they came in from the schema (defense in depth).
    for f in ("search_index_email", "search_index_phone", "search_index_last_name"):
        data.pop(f, None)
    patient = Patient(
        practice_id=practice_id,
        **data,
    )
    # Compute the search index from the plaintext values BEFORE encryption.
    # The EncryptedString type has already overwritten these with ciphertext,
    # so we compute the HMAC from the *input* dictionary we just built.
    patient.search_index_email = hmac_index(patient_in.email)
    patient.search_index_phone = hmac_index(patient_in.phone)
    patient.search_index_last_name = hmac_index(patient_in.last_name)

    db.add(patient)
    try:
        await db.commit()
    except IntegrityError:
        # M16 FIX: concurrent create racing the duplicate check — the
        # unique (practice, hmac) index makes the DB the final arbiter.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this email or phone already exists in this practice. Please verify the record."
        )
    await db.refresh(patient)

    # HIPAA: Log creation
    await log_audit_event(
        db, current_user, "patient_created", "patient", patient.id, request
    )
    await db.commit()

    return patient


@router.get("/search", response_model=List[PatientSearchRef])
async def search_patients(
    request: Request,
    query: str = Query(..., min_length=1, description="Search by name, email, or phone"),
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PatientSearchRef]:
    """Type-ahead patient lookup for the scheduling UI (tenant-scoped)."""
    q = sanitize_search_query(query)
    if not q:
        return []

    active_filter = Patient.status != PatientStatus.INACTIVE

    search_hmac = hmac_index(q)
    filters = []
    if search_hmac:
        filters.append(Patient.search_index_email == search_hmac)
        filters.append(Patient.search_index_last_name == search_hmac)
    filters.append(Patient.first_name == q)
    filters.append(Patient.last_name == q)
    stmt = (
        select(Patient)
        .where(Patient.practice_id == practice_id, active_filter, or_(*filters))
        .order_by(Patient.updated_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()

    # Bounded in-memory substring fallback for type-ahead. The patient
    # name and email columns are encrypted at rest (Fernet), so we cannot
    # push the substring match into SQL. The cap here is the practical
    # size at which the in-memory filter is still cheap for a single
    # clinician's session; it does NOT scale to multi-thousand-patient
    # practices. Migration to a Postgres trigram index (pg_trgm) over
    # the HMAC search-index columns is tracked in the audit log as a
    # known follow-up. M-3 FIX: 200 rows was 1000 before; the new cap
    # bounds latency on large practices while still comfortably
    # covering the typical type-ahead UX.
    if not matches and len(q) >= 2:
        all_result = await db.execute(
            select(Patient)
            .where(Patient.practice_id == practice_id, active_filter)
            .limit(200)
        )
        ql = q.lower()
        matches = [
            p for p in all_result.scalars().all()
            if ql in (p.first_name or "").lower()
            or ql in (p.last_name or "").lower()
            or ql in (p.email or "").lower()
            or ql in f"{(p.first_name or '').lower()} {(p.last_name or '').lower()}"
        ][:10]

    # HIPAA: Log search access
    await log_audit_event(db, current_user, "patient_searched", "patient", None, request)
    await db.commit()

    return [
        PatientSearchRef(
            id=patient.id,
            name=f"{patient.first_name or ''} {patient.last_name or ''}".strip(),
            phone=patient.phone or "",
            email=patient.email,
        )
        for patient in matches
    ]


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    request: Request,
    patient_id: UUID,
    patient_in: PatientUpdate,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
    _csrf: bool = Depends(verify_csrf),  # SECURITY FIX: CSRF protection
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """
    Update patient
    """
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Update fields
    update_data = patient_in.model_dump(exclude_unset=True)
    # F15 FIX: Strip search_index_* fields defensively (create_patient does
    # this too). If these ever enter the update schema, they could poison
    # the HMAC search indexes.
    for f in ("search_index_email", "search_index_phone", "search_index_last_name"):
        update_data.pop(f, None)

    # M16 FIX: an update used to be able to edit email/phone into a
    # collision with another record, silently defeating the create-time
    # duplicate guarantee.
    changed_contact = [f for f in ("email", "phone") if f in update_data and update_data[f]]
    if changed_contact:
        dup_filters = []
        if "email" in changed_contact:
            email_hmac = hmac_index(update_data["email"])
            if email_hmac:
                dup_filters.append(Patient.search_index_email == email_hmac)
        if "phone" in changed_contact:
            phone_hmac = hmac_index(update_data["phone"])
            if phone_hmac:
                dup_filters.append(Patient.search_index_phone == phone_hmac)
        if dup_filters:
            dup_result = await db.execute(
                select(Patient.id).where(
                    Patient.practice_id == practice_id,
                    Patient.id != patient_id,
                    Patient.status.isnot(None),
                    Patient.status != PatientStatus.INACTIVE,
                    or_(*dup_filters),
                )
            )
            if dup_result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another patient with this email or phone already exists in this practice.",
                )

    for field, value in update_data.items():
        setattr(patient, field, value)
    changed_index_fields = tuple(
        field for field in ("email", "phone", "last_name") if field in update_data
    )
    update_patient_search_indexes(patient, *changed_index_fields)

    try:
        await db.commit()
    except IntegrityError:
        # B8 FIX: a concurrent create/update could claim the same contact
        # between the precheck above and this commit; surface the unique
        # index violation as a 409 instead of an unhandled 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another patient with this email or phone already exists in this practice.",
        )
    await db.refresh(patient)

    # HIPAA: Log patient update
    await log_audit_event(
        db, current_user, "patient_updated", "patient", patient.id, request
    )
    await db.commit()

    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    request: Request,
    patient_id: UUID,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),  # SECURITY FIX: CSRF protection
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete patient (soft delete by setting status to inactive)
    """
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Soft delete
    patient.status = "inactive"

    # M15 FIX: cancelling the patient must also cancel future appointments
    # (they used to stay on the calendar and in reminder pipelines).
    from app.models.appointment import Appointment, AppointmentStatus
    future_appts = await db.execute(
        select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.practice_id == practice_id,
            Appointment.start_time >= datetime.now(timezone.utc),
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.COMPLETED,
                AppointmentStatus.NO_SHOW,
            ]),
        )
    )
    cancelled_appointments: list = []
    for apt in future_appts.scalars().all():
        apt.status = AppointmentStatus.CANCELLED
        cancelled_appointments.append(apt.id)
        # M-2 FIX: write one audit row per affected appointment so a
        # review of a single appointment row can be correlated with the
        # cancellation. The aggregate count is also included in the
        # ``patient_deleted`` row's ``changes`` payload below.
        await log_audit_event(
            db,
            current_user,
            "appointment_cancelled_patient_inactive",
            "appointment",
            apt.id,
            request,
            {"patient_id": str(patient.id), "reason": "patient_marked_inactive"},
        )

    await db.commit()

    # HIPAA: Log patient deletion (soft delete) along with the count of
    # affected future appointments so an operator can spot-check the
    # audit log when reconciling the schedule.
    await log_audit_event(
        db,
        current_user,
        "patient_deleted",
        "patient",
        patient.id,
        request,
        {"future_appointments_cancelled": len(cancelled_appointments)},
    )
    await db.commit()


def _compute_minor_ceiling_utc(
    date_of_birth: Optional[date],
    majority_age: int = 18,
    minor_retention_years: int = 7,
) -> Optional[datetime]:
    """Compute the minor-record retention ceiling (UTC-aware instant).

    docs/DATA_RETENTION_POLICY.md R1: a minor record may not be purged before
    ``date_of_birth + majority_age + minor_retention_years``. Called at
    anonymize time BEFORE DOB is scrubbed, and the resulting snapshot is
    stored on ``patients.purge_eligible_at`` so the ceiling survives erasure
    without retaining DOB/PHI.

    Returns None when the DOB is absent (caller then applies the adult rule
    only — the safe direction for a row that could be a minor).
    """
    from datetime import date as _date

    if date_of_birth is None:
        return None

    def _plus_years(d: date, years: int) -> date:
        """Exact calendar-year addition; Feb-29 snaps to Feb-28 in non-leap years."""
        try:
            return d.replace(year=d.year + max(0, years))
        except ValueError:
            return d.replace(year=d.year + max(0, years), day=28)

    majority_date = _plus_years(date_of_birth, majority_age)
    ceiling = _plus_years(majority_date, minor_retention_years)
    return datetime.combine(ceiling, datetime.min.time(), tzinfo=timezone.utc)


@router.post("/{patient_id}/anonymize", response_model=PatientResponse)
async def anonymize_patient(
    request: Request,
    patient_id: UUID,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Anonymize a patient's PHI in place (GDPR right-to-erasure).

    A hard DELETE would be blocked by historical custodial rows (invoices,
    claims, payment plans, subscriptions) that legally must be retained and
    reference this patient. Instead we irreversibly scrub every PHI column
    while keeping the (now anonymous) row for referential integrity. Portal
    access is revoked and future appointments cancelled, mirroring the soft
    delete flow. The write-once audit row records the erasure.

    NOTE: this is a one-way operation; there is no "restore".
    """
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Cancel future appointments (same policy as soft delete).
    from app.models.appointment import Appointment, AppointmentStatus
    future_appts = await db.execute(
        select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.practice_id == practice_id,
            Appointment.start_time >= datetime.now(timezone.utc),
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.COMPLETED,
                AppointmentStatus.NO_SHOW,
            ]),
        )
    )
    cancelled_appointments: list = []
    for apt in future_appts.scalars().all():
        apt.status = AppointmentStatus.CANCELLED
        cancelled_appointments.append(apt.id)

    # Revoke patient-portal access (sessions + token).
    from app.models.patient import PatientPortalSession
    await db.execute(
        PatientPortalSession.__table__.update()
        .where(
            PatientPortalSession.patient_id == patient_id,
            PatientPortalSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    patient.portal_access_token = None
    patient.portal_token_expires = None

    # Snapshot the minor-record retention ceiling BEFORE scrubbing DOB.
    # docs/DATA_RETENTION_POLICY.md R1: a minor record may not be purged before
    # date_of_birth + majority_age + minor_retention_years. We compute this at
    # anonymize time (from the practice's config, else platform defaults) and
    # store it so the ceiling survives erasure WITHOUT retaining DOB/PHI.
    from app.models.practice import Practice as _Practice
    practice_row = await db.execute(
        select(_Practice).where(_Practice.id == practice_id)
    )
    practice_obj = practice_row.scalar_one_or_none()
    _majority = (
        practice_obj.majority_age if practice_obj and practice_obj.majority_age else 18
    )
    _minor_years = (
        practice_obj.minor_retention_years
        if practice_obj and practice_obj.minor_retention_years
        else 7
    )
    patient.purge_eligible_at = _compute_minor_ceiling_utc(
        patient.date_of_birth, _majority, _minor_years
    )

    patient_email = patient.email

    # Scrub every PHI column. Search HMACs must go too or the patient
    # remains findable by email/phone/name equality lookups.
    # NOTE: date_of_birth is NOT NULL at the storage layer; it is scrubbed to
    # the 1970-01-01 sentinel (DOB is only sensitive in combination with the
    # name, which is gone). Revisit with a nullable migration if counsel
    # prefers NULL.
    patient.first_name = "[deleted]"
    patient.last_name = "[deleted]"
    patient.date_of_birth = datetime(1970, 1, 1).date()
    patient.gender = None
    patient.email = None
    patient.phone = None
    patient.address_street = None
    patient.address_city = None
    patient.address_state = None
    patient.address_zip = None
    patient.abha_id = None
    patient.ssn_last_four = None
    patient.emergency_contact = {}
    patient.medical_alerts = []
    patient.medical_history = {}
    patient.dental_history = {}
    patient.insurance_info = None
    patient.search_index_email = None
    patient.search_index_phone = None
    patient.search_index_last_name = None
    patient.status = PatientStatus.INACTIVE

    # Scrub child records free-text and identifying PHI (Decision 7 / H5)
    from app.models.clinical import DentalChart, PerioChart
    from app.models.referral import Referral
    from app.models.communication import PatientMessage, Conversation, ConversationMessage
    from app.models.booking import OnlineBooking, WaitlistEntry
    from app.models.treatment import TreatmentPlan, TreatmentProcedure
    from app.models.document import Document
    from app.models.patient import PatientPortalAccessCode

    # 1. Clinical notes
    await db.execute(
        update(ClinicalNote)
        .where(ClinicalNote.patient_id == patient_id)
        .values(
            content="[redacted]",
            subjective="[redacted]",
            objective="[redacted]",
            assessment="[redacted]",
            plan="[redacted]",
            signed_by="[redacted]",
            attachments=[],
        )
    )
    # 2. Dental chart & Perio chart
    await db.execute(
        update(DentalChart)
        .where(DentalChart.patient_id == patient_id)
        .values(chart_data={})
    )
    await db.execute(
        update(PerioChart)
        .where(PerioChart.patient_id == patient_id)
        .values(notes=None, diagnosis=None, perio_data={})
    )
    # 3. Referrals
    await db.execute(
        update(Referral)
        .where(Referral.patient_id == patient_id)
        .values(
            reason="[redacted]",
            clinical_notes=None,
            outcome=None,
            follow_up_notes=None,
        )
    )
    # 4. Communications: PatientMessage, Conversation, ConversationMessage
    await db.execute(
        update(PatientMessage)
        .where(PatientMessage.patient_id == patient_id)
        .values(
            subject="[redacted]",
            content="[redacted]",
            recipient_phone=None,
            recipient_email=None,
            attachments=None,
            error_message=None,
        )
    )
    conv_res = await db.execute(
        select(Conversation.id).where(Conversation.patient_id == patient_id)
    )
    conv_ids = conv_res.scalars().all()
    if conv_ids:
        await db.execute(
            update(ConversationMessage)
            .where(ConversationMessage.conversation_id.in_(conv_ids))
            .values(content="[redacted]", attachments=None)
        )
    await db.execute(
        update(Conversation)
        .where(Conversation.patient_id == patient_id)
        .values(subject="[redacted]", last_message_preview="[redacted]")
    )
    # 5. Appointments notes and cancellation reason
    await db.execute(
        update(Appointment)
        .where(Appointment.patient_id == patient_id)
        .values(notes=None, cancellation_reason="[redacted]")
    )
    # 6. Online bookings and waitlist entries
    await db.execute(
        update(OnlineBooking)
        .where(OnlineBooking.patient_id == patient_id)
        .values(
            first_name="[deleted]",
            last_name="[deleted]",
            email="[deleted]",
            phone="[deleted]",
            date_of_birth=None,
            reason=None,
            chief_complaint=None,
            insurance_carrier_name=None,
            insurance_member_id=None,
            insurance_group_number=None,
            medical_history={},
            intake_form_responses={},
            patient_notes=None,
            staff_notes=None,
            cancellation_reason=None,
        )
    )
    await db.execute(
        update(WaitlistEntry)
        .where(WaitlistEntry.patient_id == patient_id)
        .values(
            first_name="[deleted]",
            last_name="[deleted]",
            email="[deleted]",
            phone="[deleted]",
            reason=None,
        )
    )
    # 7. Treatment plans and procedures
    plan_res = await db.execute(
        select(TreatmentPlan.id).where(TreatmentPlan.patient_id == patient_id)
    )
    plan_ids = plan_res.scalars().all()
    if plan_ids:
        await db.execute(
            update(TreatmentProcedure)
            .where(TreatmentProcedure.treatment_plan_id.in_(plan_ids))
            .values(acceptance_notes=None)
        )
    await db.execute(
        update(TreatmentPlan)
        .where(TreatmentPlan.patient_id == patient_id)
        .values(
            chief_complaint=None,
            diagnosis=None,
            treatment_goals=None,
            acceptance_notes=None,
            notes=None,
        )
    )
    # 8. Documents
    await db.execute(
        update(Document)
        .where(Document.patient_id == patient_id)
        .values(description=None, content=None)
    )
    # 9. Portal access codes and lockout
    await db.execute(
        delete(PatientPortalAccessCode).where(
            PatientPortalAccessCode.patient_id == patient_id
        )
    )
    if patient_email and practice_obj and practice_obj.public_slug:
        from app.models.portal_lockout import PortalIdentityLockout
        await db.execute(
            delete(PortalIdentityLockout).where(
                PortalIdentityLockout.practice_slug == practice_obj.public_slug,
                PortalIdentityLockout.email == str(patient_email).lower(),
            )
        )

    await log_audit_event(
        db,
        current_user,
        "patient_anonymized",
        "patient",
        patient.id,
        request,
        {
            "scrubbed_fields": [
                "first_name", "last_name", "date_of_birth", "gender",
                "email", "phone", "address", "abha_id", "ssn_last_four",
                "emergency_contact", "medical_history", "dental_history",
                "insurance_info", "search_indexes", "portal_access",
            ],
            "scrubbed_child_records": [
                "clinical_notes", "dental_charts", "perio_charts",
                "referrals", "patient_messages", "conversations",
                "appointments", "online_bookings", "waitlist_entries",
                "treatment_plans", "documents", "portal_lockouts",
            ],
            "future_appointments_cancelled": len(cancelled_appointments),
        },
    )
    await db.commit()

    # Reload so the response has consistent clean state.
    await db.refresh(patient)
    return patient


@router.get("/{patient_id}/export", response_model=PatientExportResponse)
async def export_patient_data(
    request: Request,
    patient_id: UUID,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PatientExportResponse:
    """
    GDPR Right to Data Portability / HIPAA Patient Export.
    Exports all personal data and PHI related to the patient in a structured format.
    """
    from app.models import (
        Appointment,
        ClinicalNote,
        TreatmentPlan,
        Invoice,
        Payment,
        PatientInsurance,
        InsuranceClaim,
        PatientImage,
        Document,
    )

    # 1. Fetch patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # 2. Fetch related data.
    #
    # H-06 FIX: every child query now carries its own practice predicate.
    # Previously they filtered on patient_id alone, trusting that a
    # practice-scoped patient implies practice-scoped children. That is an
    # assumption about data consistency, not an enforced invariant -- and this
    # endpoint emits a complete PHI export, so any cross-tenant or orphaned
    # child row attached to that patient id would be disclosed.
    #
    # Models carrying practice_id are filtered directly. ClinicalNote,
    # PatientInsurance and Payment have no practice_id column, so they are
    # joined to their practice-scoped parent instead (patient / invoice).
    appointments_result = await db.execute(
        select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.practice_id == practice_id,
        )
    )
    appointments = appointments_result.scalars().all()

    notes_result = await db.execute(
        select(ClinicalNote)
        .join(Patient, Patient.id == ClinicalNote.patient_id)
        .where(
            ClinicalNote.patient_id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    notes = notes_result.scalars().all()

    plans_result = await db.execute(
        select(TreatmentPlan).where(
            TreatmentPlan.patient_id == patient_id,
            TreatmentPlan.practice_id == practice_id,
        )
    )
    plans = plans_result.scalars().all()

    invoices_result = await db.execute(
        select(Invoice).where(
            Invoice.patient_id == patient_id,
            Invoice.practice_id == practice_id,
        )
    )
    invoices = invoices_result.scalars().all()

    payments_result = await db.execute(
        select(Payment)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(
            Payment.patient_id == patient_id,
            Invoice.practice_id == practice_id,
        )
    )
    payments = payments_result.scalars().all()

    insurance_result = await db.execute(
        select(PatientInsurance)
        .join(Patient, Patient.id == PatientInsurance.patient_id)
        .where(
            PatientInsurance.patient_id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    insurances = insurance_result.scalars().all()

    claims_result = await db.execute(
        select(InsuranceClaim).where(
            InsuranceClaim.patient_id == patient_id,
            InsuranceClaim.practice_id == practice_id,
        )
    )
    claims = claims_result.scalars().all()

    images_result = await db.execute(
        select(PatientImage).where(
            PatientImage.patient_id == patient_id,
            PatientImage.practice_id == practice_id,
        )
    )
    images = images_result.scalars().all()

    docs_result = await db.execute(
        select(Document).where(
            Document.patient_id == patient_id,
            Document.practice_id == practice_id,
        )
    )
    docs = docs_result.scalars().all()

    # 3. Log HIPAA Audit Event
    await log_audit_event(
        db, current_user, "patient_data_exported", "patient", patient.id, request
    )
    await db.commit()

    # 4. Construct JSON payload
    def model_to_dict(model_obj) -> dict:
        if not model_obj:
            return {}
        res = {}
        for col in model_obj.__table__.columns:
            if col.name.startswith("search_index_") or col.name.startswith("portal_"):
                continue
            val = getattr(model_obj, col.name)
            if isinstance(val, UUID):
                res[col.name] = str(val)
            elif isinstance(val, (date, datetime)):
                res[col.name] = val.isoformat()
            elif hasattr(val, 'value'): # Enum
                res[col.name] = val.value
            else:
                res[col.name] = val
        return res

    exported_by_name = (
        current_user.full_name
        if hasattr(current_user, 'full_name')
        else f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
    )

    return {
        "exported_at": datetime.now(timezone.utc),
        "exported_by": {
            "id": str(current_user.id),
            "name": exported_by_name,
            "role": current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
        },
        "patient_demographics": model_to_dict(patient),
        "appointments": [model_to_dict(apt) for apt in appointments],
        "clinical_notes": [model_to_dict(note) for note in notes],
        "treatment_plans": [model_to_dict(plan) for plan in plans],
        "invoices": [model_to_dict(inv) for inv in invoices],
        "payments": [model_to_dict(pay) for pay in payments],
        "insurances": [model_to_dict(ins) for ins in insurances],
        "insurance_claims": [model_to_dict(claim) for claim in claims],
        "patient_images": [model_to_dict(img) for img in images],
        "documents": [model_to_dict(doc) for doc in docs],
    }

@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    request: Request,
    patient_id: UUID,
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """
    Get patient by ID
    """
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # HIPAA: Log PHI read access
    await log_audit_event(
        db, current_user, "patient_viewed", "patient", patient.id, request
    )
    await db.commit()

    # EXPERT HARDENING: Adaptive PHI Visibility (Least Privilege)
    # Front-Desk and Hygienists don't need access to specific insurance IDs/keys unless authorized.
    # F16 FIX: Redact on a serialized copy, NOT on the ORM instance.
    # Mutating the ORM instance risks persisting the redacted blob if the
    # session ever flushes. We build the response dict and redact there.
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST]:
        # Return a shallow copy with insurance_info redacted
        # PatientResponse is a Pydantic model; we can't easily copy it,
        # so we expunge the instance from the session before mutating
        # to guarantee the redacted value is never flushed to the DB.
        db.expunge(patient)
        if patient.insurance_info:
             patient.insurance_info = {"status": "present", "redacted": True, "note": "Contact Admin for details"}

    from app.models.document import Document
    from app.utils.storage import storage as file_storage

    doc_res = await db.execute(
        select(Document).where(
            Document.patient_id == patient.id,
            Document.practice_id == practice_id,
            Document.file_url.isnot(None),
        ).order_by(Document.created_at.desc())
    )
    docs = doc_res.scalars().all()
    attachments = []
    for doc in docs:
        meta = {}
        if doc.notes:
            try:
                meta = json.loads(doc.notes)
            except Exception:
                meta = {}
        file_url = file_storage.get_url(doc.file_url) if doc.file_url else ""
        if not file_url and doc.file_url:
            file_url = f"/uploads/{doc.file_url}"
        attachments.append({
            "id": doc.id,
            "name": doc.name,
            "type": meta.get("mime_type") or f"application/{doc.file_type or 'octet-stream'}",
            "size": meta.get("size", 0),
            "url": file_url,
            "category": meta.get("category") or (doc.category.value if hasattr(doc.category, 'value') else str(doc.category or 'other')).lower(),
            "uploaded_at": doc.created_at,
            "uploaded_by": str(doc.created_by) if doc.created_by else None,
            "uploaded_by_name": "Staff",
        })
    patient.attachments = attachments

    return patient


@router.get("/{patient_id}/notes", response_model=List[ClinicalNoteResponse])
async def list_patient_notes(
    patient_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> List[ClinicalNoteResponse]:
    """List clinical notes for a patient (tenant-scoped, newest first).

    Consistent with the /notes router: reading clinical-note PHI requires a
    clinical role; front-desk/admin-only accounts get 403.
    """
    await _get_patient_or_404(db, patient_id, current_user)
    result = await db.execute(
        select(ClinicalNote)
        .options(selectinload(ClinicalNote.provider))
        .where(ClinicalNote.patient_id == patient_id)
        .order_by(ClinicalNote.created_at.desc())
    )
    notes = result.scalars().all()
    await log_audit_event(
        db, current_user, "clinical_notes_listed", "clinical_note", patient_id, request
    )
    await db.commit()
    return [_to_response(n) for n in notes]


# ── Dental Charting Endpoints ──────────────────────────────────────────

TOOTH_NAMES = {
    1: "Upper Right 3rd Molar (Wisdom)",
    2: "Upper Right 2nd Molar",
    3: "Upper Right 1st Molar",
    4: "Upper Right 2nd Premolar",
    5: "Upper Right 1st Premolar",
    6: "Upper Right Canine",
    7: "Upper Right Lateral Incisor",
    8: "Upper Right Central Incisor",
    9: "Upper Left Central Incisor",
    10: "Upper Left Lateral Incisor",
    11: "Upper Left Canine",
    12: "Upper Left 1st Premolar",
    13: "Upper Left 2nd Premolar",
    14: "Upper Left 1st Molar",
    15: "Upper Left 2nd Molar",
    16: "Upper Left 3rd Molar (Wisdom)",
    17: "Lower Left 3rd Molar (Wisdom)",
    18: "Lower Left 2nd Molar",
    19: "Lower Left 1st Molar",
    20: "Lower Left 2nd Premolar",
    21: "Lower Left 1st Premolar",
    22: "Lower Left Canine",
    23: "Lower Left Lateral Incisor",
    24: "Lower Left Central Incisor",
    25: "Lower Right Central Incisor",
    26: "Lower Right Lateral Incisor",
    27: "Lower Right Canine",
    28: "Lower Right 1st Premolar",
    29: "Lower Right 2nd Premolar",
    30: "Lower Right 1st Molar",
    31: "Lower Right 2nd Molar",
    32: "Lower Right 3rd Molar (Wisdom)",
}


async def _lock_patient_for_chart_write(
    db: AsyncSession, patient_id: UUID, current_user: User
) -> Patient:
    """Load the patient row under ``SELECT ... FOR UPDATE`` for chart writes.

    CONCURRENCY: the whole dental chart lives in the single ``dental_history``
    JSON column, so every tooth write is a read-modify-write of the *entire*
    blob. Without a row lock, two clinicians editing two different teeth at the
    same time both read the same history, each adds their own tooth, and the
    second commit silently discards the first one's clinical entry. Locking the
    row serialises the read-modify-write so edits merge instead of racing.

    ``FOR UPDATE`` is a no-op on SQLite (the dialect omits the clause), which is
    acceptable: SQLite is dev/test only and is single-writer anyway.
    """
    result = await db.execute(
        select(Patient)
        .where(
            Patient.id == patient_id,
            Patient.practice_id == current_user.practice_id,
        )
        .with_for_update()
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or access denied",
        )
    return patient


def _build_default_chart(patient: Patient) -> dict:
    history = patient.dental_history or {}
    teeth_dict = history.get("teeth", {}) if isinstance(history, dict) else {}
    teeth = []
    for num in range(1, 33):
        t_data = teeth_dict.get(str(num), {})
        teeth.append({
            "number": num,
            "name": TOOTH_NAMES.get(num, f"Tooth {num}"),
            "condition": t_data.get("condition", "sound"),
            "surfaces": t_data.get("surfaces", []),
            "procedures": t_data.get("procedures", []),
        })
    return {
        "id": f"chart_{patient.id}",
        "patientId": str(patient.id),
        "patientName": f"{patient.first_name} {patient.last_name}",
        "teeth": teeth,
        "updatedAt": history.get("updated_at", datetime.now(timezone.utc).isoformat()) if isinstance(history, dict) else datetime.now(timezone.utc).isoformat(),
        "lastUpdated": history.get("updated_at", datetime.now(timezone.utc).isoformat()) if isinstance(history, dict) else datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{patient_id}/chart")
async def get_patient_dental_chart(
    patient_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get dental chart for a patient"""
    patient = await _get_patient_or_404(db, patient_id, current_user)
    await log_audit_event(db, current_user, "dental_chart_viewed", "dental_chart", patient.id, request)
    await db.commit()
    return _build_default_chart(patient)


@router.put("/{patient_id}/chart/teeth/{tooth_number}/condition")
async def update_tooth_condition(
    patient_id: UUID,
    tooth_number: int,
    payload: dict,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update condition for a specific tooth"""
    if tooth_number < 1 or tooth_number > 32:
        raise HTTPException(status_code=400, detail="Tooth number must be between 1 and 32")

    patient = await _lock_patient_for_chart_write(db, patient_id, current_user)
    history = dict(patient.dental_history or {}) if isinstance(patient.dental_history, dict) else {}
    teeth = dict(history.get("teeth", {}))
    tooth = dict(teeth.get(str(tooth_number), {}))
    tooth["condition"] = payload.get("condition", "sound")
    if "surfaces" in payload:
        tooth["surfaces"] = payload["surfaces"]
    teeth[str(tooth_number)] = tooth
    history["teeth"] = teeth
    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    patient.dental_history = history

    await log_audit_event(
        db, current_user, "update_tooth_condition", "dental_chart", patient.id, request,
        {"tooth": tooth_number, "condition": payload.get("condition")}
    )
    await db.commit()
    return _build_default_chart(patient)


@router.post("/{patient_id}/chart/teeth/{tooth_number}/procedures")
async def add_tooth_procedure(
    patient_id: UUID,
    tooth_number: int,
    procedure_data: dict,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Add procedure to a tooth"""
    if tooth_number < 1 or tooth_number > 32:
        raise HTTPException(status_code=400, detail="Tooth number must be between 1 and 32")

    from uuid import uuid4
    patient = await _lock_patient_for_chart_write(db, patient_id, current_user)
    history = dict(patient.dental_history or {}) if isinstance(patient.dental_history, dict) else {}
    teeth = dict(history.get("teeth", {}))
    tooth = dict(teeth.get(str(tooth_number), {}))
    procedures = list(tooth.get("procedures", []))

    raw_cost = procedure_data.get("cost", 0.0)
    try:
        cost_decimal = Decimal(str(raw_cost if raw_cost is not None else 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid procedure cost",
        )
    if cost_decimal < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Procedure cost cannot be negative",
        )

    new_proc = {
        "id": str(uuid4()),
        "code": procedure_data.get("code", "D0150"),
        "description": procedure_data.get("description", "Procedure"),
        "surface": procedure_data.get("surface"),
        # L-3 FIX: persist money as quantized decimal string, not binary
        # float — float(cost) drifts on re-read (Decimal(str(float))).
        "cost": str(cost_decimal),
        "status": procedure_data.get("status", "planned"),
        "date": procedure_data.get("date", datetime.now(timezone.utc).date().isoformat()),
        "notes": procedure_data.get("notes"),
    }
    procedures.append(new_proc)
    tooth["procedures"] = procedures
    teeth[str(tooth_number)] = tooth
    history["teeth"] = teeth
    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    patient.dental_history = history

    await log_audit_event(
        db, current_user, "add_tooth_procedure", "dental_chart", patient.id, request,
        {"tooth": tooth_number, "procedure": new_proc}
    )
    await db.commit()
    return new_proc


@router.put("/{patient_id}/chart/teeth/{tooth_number}/procedures/{procedure_id}/status")
async def update_tooth_procedure_status(
    patient_id: UUID,
    tooth_number: int,
    procedure_id: str,
    status_data: dict,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update status of a tooth procedure"""
    patient = await _lock_patient_for_chart_write(db, patient_id, current_user)
    history = dict(patient.dental_history or {}) if isinstance(patient.dental_history, dict) else {}
    teeth = dict(history.get("teeth", {}))
    tooth = dict(teeth.get(str(tooth_number), {}))
    procedures = list(tooth.get("procedures", []))

    found = False
    for p in procedures:
        if p.get("id") == procedure_id:
            p["status"] = status_data.get("status", "completed")
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Procedure not found on tooth")

    tooth["procedures"] = procedures
    teeth[str(tooth_number)] = tooth
    history["teeth"] = teeth
    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    patient.dental_history = history

    await log_audit_event(
        db, current_user, "update_tooth_procedure_status", "dental_chart", patient.id, request,
        {"tooth": tooth_number, "procedure_id": procedure_id, "status": status_data.get("status")}
    )
    await db.commit()
    return {"status": "success"}


@router.delete("/{patient_id}/chart/teeth/{tooth_number}/procedures/{procedure_id}")
async def delete_tooth_procedure(
    patient_id: UUID,
    tooth_number: int,
    procedure_id: str,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Delete a tooth procedure"""
    patient = await _lock_patient_for_chart_write(db, patient_id, current_user)
    history = dict(patient.dental_history or {}) if isinstance(patient.dental_history, dict) else {}
    teeth = dict(history.get("teeth", {}))
    tooth = dict(teeth.get(str(tooth_number), {}))
    procedures = [p for p in tooth.get("procedures", []) if p.get("id") != procedure_id]
    tooth["procedures"] = procedures
    teeth[str(tooth_number)] = tooth
    history["teeth"] = teeth
    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    patient.dental_history = history

    await log_audit_event(
        db, current_user, "delete_tooth_procedure", "dental_chart", patient.id, request,
        {"tooth": tooth_number, "procedure_id": procedure_id}
    )
    await db.commit()
    return {"status": "success"}


# ── Status and Note Management Endpoints ──────────────────────────────

@router.put("/{id}/status")
async def update_patient_status(
    id: UUID,
    payload: dict,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Update patient active/inactive status."""
    patient = await _get_patient_or_404(db, id, current_user)
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing status")
    try:
        patient.status = PatientStatus(new_status.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    await log_audit_event(
        db, current_user, "patient_status_updated", "patient", patient.id, request,
        {"status": patient.status.value}
    )
    await db.commit()
    return {"status": patient.status.value, "message": "Patient status updated"}


@router.post("/{patient_id}/notes")
async def create_patient_note(
    patient_id: UUID,
    payload: dict,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Add a note to a patient record."""
    from app.models.clinical import NoteType
    await _get_patient_or_404(db, patient_id, current_user)
    raw_type = (payload.get("category") or payload.get("note_type") or "general").lower()
    try:
        note_type = NoteType(raw_type)
    except ValueError:
        note_type = NoteType.GENERAL

    note = ClinicalNote(
        patient_id=patient_id,
        provider_id=current_user.id,
        note_type=note_type,
        content=payload.get("content") or payload.get("text") or "",
        subjective=payload.get("subjective"),
        objective=payload.get("objective"),
        assessment=payload.get("assessment"),
        plan=payload.get("plan"),
    )
    db.add(note)
    await log_audit_event(
        db, current_user, "clinical_note_created", "clinical_note", patient_id, request
    )
    await db.commit()
    await db.refresh(note)
    return {
        "id": str(note.id),
        "title": payload.get("title") or "Clinical Note",
        "content": note.content or "",
        "category": note.note_type.value if hasattr(note.note_type, 'value') else str(note.note_type),
        "createdAt": note.created_at.isoformat() if note.created_at else datetime.now(timezone.utc).isoformat(),
        "providerName": f"{current_user.first_name} {current_user.last_name}",
    }


@router.delete("/{patient_id}/notes/{note_id}")
async def delete_patient_note(
    patient_id: UUID,
    note_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Delete a patient clinical note."""
    await _get_patient_or_404(db, patient_id, current_user)
    result = await db.execute(
        select(ClinicalNote).where(
            ClinicalNote.id == note_id,
            ClinicalNote.patient_id == patient_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await log_audit_event(
        db, current_user, "clinical_note_deleted", "clinical_note", note_id, request
    )
    await db.commit()
    return {"message": "Note deleted successfully"}


# ── Decision 3: Two-Stage Data Migration (Dry-Run & Commit) ────────────

@router.post("/import/dry-run")
async def import_patients_dry_run(
    payload: dict,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Stage 1: Validate rows, parse DOB/phone/email, check conflicts, return preview."""
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Invalid payload: expected 'rows' list")

    total_rows = len(rows)
    valid_rows = []
    errors = []
    duplicates = []

    for idx, r in enumerate(rows):
        row_num = idx + 1
        fn = (r.get("first_name") or r.get("firstName") or "").strip()
        ln = (r.get("last_name") or r.get("lastName") or "").strip()
        raw_dob = r.get("date_of_birth") or r.get("dob")
        email = (r.get("email") or "").strip()
        phone = (r.get("phone") or "").strip()

        if not fn or not ln:
            errors.append(f"Row {row_num}: First and last name are required.")
            continue

        parsed_dob = None
        if raw_dob:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    parsed_dob = datetime.strptime(str(raw_dob).strip(), fmt).date()
                    break
                except ValueError:
                    pass
        if not parsed_dob:
            errors.append(f"Row {row_num}: Missing or invalid date_of_birth (YYYY-MM-DD or MM/DD/YYYY required).")
            continue

        # Check existing duplicates in practice
        dup_filters = []
        if email:
            em_h = hmac_index(email)
            if em_h:
                dup_filters.append(Patient.search_index_email == em_h)
        if phone:
            ph_h = hmac_index(phone)
            if ph_h:
                dup_filters.append(Patient.search_index_phone == ph_h)

        is_dup = False
        if dup_filters:
            dup_stmt = select(Patient.id).where(
                Patient.practice_id == current_user.practice_id,
                or_(*dup_filters),
            ).limit(1)
            dup_res = await db.execute(dup_stmt)
            if dup_res.scalar_one_or_none():
                is_dup = True
                duplicates.append(f"Row {row_num}: Patient with matching email/phone already exists.")

        if not is_dup:
            valid_rows.append({
                "row_num": row_num,
                "first_name": fn,
                "last_name": ln,
                "date_of_birth": parsed_dob.isoformat(),
                "email": email or None,
                "phone": phone or None,
                "gender": (r.get("gender") or "other").lower(),
            })

    return {
        "total_rows": total_rows,
        "valid_count": len(valid_rows),
        "duplicate_count": len(duplicates),
        "error_count": len(errors),
        "errors": errors[:50],
        "duplicates": duplicates[:50],
        "preview": valid_rows[:10],
    }


@router.post("/import/commit")
async def import_patients_commit(
    payload: dict,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
    _quota: None = Depends(enforce_plan_quota("patients")),
):
    """Stage 2: Transactional commit of validated migration rows."""
    from app.models.patient import Gender
    rows = payload.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="No rows provided for import")

    imported = []
    for r in rows:
        fn = (r.get("first_name") or r.get("firstName") or "").strip()
        ln = (r.get("last_name") or r.get("lastName") or "").strip()
        raw_dob = r.get("date_of_birth") or r.get("dob")
        dob = None
        if raw_dob:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    dob = datetime.strptime(str(raw_dob).strip(), fmt).date()
                    break
                except ValueError:
                    pass
        if not fn or not ln or not dob:
            continue

        raw_gender = (r.get("gender") or "other").lower()
        gender = Gender.OTHER
        if raw_gender in ("male", "m"):
            gender = Gender.MALE
        elif raw_gender in ("female", "f"):
            gender = Gender.FEMALE

        patient = Patient(
            practice_id=current_user.practice_id,
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            email=r.get("email"),
            phone=r.get("phone"),
            status=PatientStatus.ACTIVE,
        )
        update_patient_search_indexes(patient, "email", "phone", "last_name")
        db.add(patient)
        imported.append(patient)

    await db.commit()
    await log_audit_event(
        db, current_user, "patients_bulk_imported", "practice", current_user.practice_id, request,
        {"count": len(imported)}
    )

    return {
        "success": True,
        "imported_count": len(imported),
        "imported_ids": [str(p.id) for p in imported],
        "message": f"Successfully imported {len(imported)} patient records",
    }


@router.post("/{patient_id}/attachments")
@limiter.limit("30/minute")
async def upload_patient_attachment(
    patient_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("other"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Upload a file attachment for a patient record."""
    patient = await _get_patient_or_404(db, patient_id, current_user)

    from app.core.file_security import read_stream_with_size_limit, scan_and_validate_file, sanitize_filename
    from app.core.config_simple import settings
    from app.utils.storage import storage as file_storage
    from app.models.document import Document, DocumentCategory, DocumentStatus

    # 20 MB size limit
    max_attachment_size = 20 * 1024 * 1024
    try:
        content = await read_stream_with_size_limit(file, max_attachment_size)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Attachment too large (max 20MB): {exc}",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    safe_name = sanitize_filename(file.filename or "attachment")
    ext = os.path.splitext(safe_name)[1].lower()
    allowed_exts = ["pdf", "jpg", "jpeg", "png", "webp", "doc", "docx", "txt", "tiff", "bmp"]

    try:
        scan_res = await scan_and_validate_file(
            file_content=content,
            filename=safe_name,
            allowed_extensions=allowed_exts,
            max_size=max_attachment_size,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security validation failed: {exc}",
        )

    detected_mime = scan_res.get("mime_type", file.content_type or "application/octet-stream")

    # Map category to DocumentCategory enum
    category_norm = (category or "other").strip().lower()
    category_map = {
        "consent": DocumentCategory.CONSENT,
        "financial": DocumentCategory.FINANCIAL,
        "insurance": DocumentCategory.FINANCIAL,
        "clinical": DocumentCategory.CLINICAL,
        "xray": DocumentCategory.CLINICAL,
        "referral": DocumentCategory.CLINICAL,
        "administrative": DocumentCategory.ADMINISTRATIVE,
        "policy": DocumentCategory.POLICY,
        "marketing": DocumentCategory.MARKETING,
    }
    doc_category = category_map.get(category_norm, DocumentCategory.OTHER)

    # Store partitioned by practice and patient
    unique_token = secrets.token_hex(8)
    destination = f"practices/{current_user.practice_id}/patients/{patient_id}/attachments/{unique_token}{ext}"
    storage_path = file_storage.upload(content, destination, detected_mime)

    meta = {
        "size": len(content),
        "mime_type": detected_mime,
        "category": category_norm,
        "original_name": file.filename or safe_name,
    }

    doc = Document(
        id=uuid.uuid4(),
        practice_id=current_user.practice_id,
        patient_id=patient.id,
        created_by=current_user.id,
        name=safe_name,
        category=doc_category,
        file_url=destination,
        file_type=ext.lstrip("."),
        status=DocumentStatus.SIGNED,
        notes=json.dumps(meta),
    )
    db.add(doc)
    await log_audit_event(
        db, current_user, "patient_attachment_uploaded", "patient", patient_id, request,
        {"filename": safe_name, "size": len(content), "mime_type": detected_mime}
    )
    await db.commit()
    await db.refresh(doc)

    file_url = file_storage.get_url(destination)
    if not file_url:
        file_url = f"/uploads/{destination}"

    creator_name = f"{current_user.first_name} {current_user.last_name}".strip() or "Staff"

    return {
        "id": str(doc.id),
        "name": doc.name,
        "type": detected_mime,
        "size": len(content),
        "url": file_url,
        "category": category_norm,
        "uploaded_at": doc.created_at.isoformat() if doc.created_at else datetime.now(timezone.utc).isoformat(),
        "uploaded_by": str(current_user.id),
        "uploaded_by_name": creator_name,
    }


@router.get("/{patient_id}/attachments")
async def list_patient_attachments(
    patient_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List file attachments for a patient record."""
    patient = await _get_patient_or_404(db, patient_id, current_user)

    from app.models.document import Document
    from app.utils.storage import storage as file_storage
    from app.models.user import User as UserModel

    stmt = select(Document, UserModel).outerjoin(
        UserModel, Document.created_by == UserModel.id
    ).where(
        Document.patient_id == patient.id,
        Document.practice_id == current_user.practice_id,
        Document.file_url.isnot(None),
    ).order_by(Document.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    attachments = []
    for doc, creator in rows:
        meta = {}
        if doc.notes:
            try:
                meta = json.loads(doc.notes)
            except Exception:
                meta = {}

        file_url = file_storage.get_url(doc.file_url) if doc.file_url else ""
        if not file_url and doc.file_url:
            file_url = f"/uploads/{doc.file_url}"

        creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else "Staff"

        attachments.append({
            "id": str(doc.id),
            "name": doc.name,
            "type": meta.get("mime_type") or f"application/{doc.file_type or 'octet-stream'}",
            "size": meta.get("size", 0),
            "url": file_url,
            "category": meta.get("category") or (doc.category.value if hasattr(doc.category, 'value') else str(doc.category or 'other')).lower(),
            "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
            "uploaded_by": str(doc.created_by) if doc.created_by else "",
            "uploaded_by_name": creator_name,
        })

    await log_audit_event(
        db, current_user, "patient_attachments_listed", "patient", patient_id, request
    )
    return attachments


@router.delete("/{patient_id}/attachments/{attachment_id}")
async def delete_patient_attachment(
    patient_id: UUID,
    attachment_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Delete a patient attachment."""
    patient = await _get_patient_or_404(db, patient_id, current_user)

    from app.models.document import Document
    from app.utils.storage import storage as file_storage

    result = await db.execute(
        select(Document).where(
            Document.id == attachment_id,
            Document.patient_id == patient.id,
            Document.practice_id == current_user.practice_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    if doc.file_url:
        try:
            file_storage.delete(doc.file_url)
        except Exception as exc:
            logger.warning("Failed to delete storage file %s: %s", doc.file_url, exc)

    await db.delete(doc)
    await log_audit_event(
        db, current_user, "patient_attachment_deleted", "patient", patient_id, request,
        {"attachment_id": str(attachment_id), "filename": doc.name}
    )
    await db.commit()
    return {"success": True, "message": "Attachment deleted successfully"}
