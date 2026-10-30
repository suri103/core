"""
Clinical Notes Endpoints
CRUD for clinical notes (SOAP + free-text). Mounted at /notes.
Sibling route GET /patients/{patient_id}/notes lives in patients.py and reuses
the helpers below.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.models.user import User, UserRole
from app.api.deps import require_role, verify_csrf
from app.models.clinical import ClinicalNote, NoteType
from app.models.patient import Patient
from app.schemas.clinical import (
    ClinicalNoteCreate,
    ClinicalNoteUpdate,
    ClinicalNoteResponse,
)
from app.core.audit import log_audit_event
from app.services.tenant_refs import require_appointment, require_provider

router = APIRouter()

CLINICAL_ROLES = (UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)

# H-05 FIX: roles that may be recorded as the treating provider on a note.
# The provider is a clinical attribution, so a front-desk or admin-only
# account must not be nameable as the author of clinical findings.
NOTE_PROVIDER_ROLES = (UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)


async def _validate_note_references(
    db: AsyncSession,
    current_user: User,
    patient_id: UUID,
    provider_id: Optional[UUID],
    appointment_id: Optional[UUID],
) -> None:
    """H-05 FIX: prove provider and appointment belong here before writing them.

    The patient was already tenant-checked by the caller, but provider_id and
    appointment_id came straight from the request body and were written
    unvalidated -- so a note could be attributed to another practice's
    clinician, or linked to another practice's (or another patient's)
    appointment, and the response then serialized that provider's name.
    """
    if provider_id is not None:
        await require_provider(
            db,
            provider_id,
            current_user.practice_id,
            field="Provider",
            roles=NOTE_PROVIDER_ROLES,
        )
    if appointment_id is not None:
        await require_appointment(
            db,
            appointment_id,
            current_user.practice_id,
            patient_id=patient_id,
            field="Appointment",
        )


def _provider_name(note: ClinicalNote) -> str:
    """Best-effort display name from the (eager-loaded) provider relationship."""
    provider = getattr(note, "provider", None)
    if provider is None:
        return ""
    first = provider.first_name or ""
    last = provider.last_name or ""
    return f"{first} {last}".strip()


def _to_response(note: ClinicalNote, provider_name: Optional[str] = None) -> ClinicalNoteResponse:
    return ClinicalNoteResponse(
        id=note.id,
        patient_id=note.patient_id,
        provider_id=note.provider_id,
        provider_name=provider_name if provider_name is not None else _provider_name(note),
        appointment_id=note.appointment_id,
        type=note.note_type.value if note.note_type else "",
        content=note.content,
        subjective=note.subjective,
        objective=note.objective,
        assessment=note.assessment,
        plan=note.plan,
        attachments=note.attachments,
        signed_at=note.signed_at,
        signed_by=note.signed_by,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


async def _get_patient_or_404(
    db: AsyncSession, patient_id: UUID, current_user: User
) -> Patient:
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
            detail="Patient not found or access denied",
        )
    return patient


async def _get_note_or_404(
    db: AsyncSession, note_id: UUID, current_user: User
) -> ClinicalNote:
    # Join-scoped first query: never load a foreign-practice row into memory.
    result = await db.execute(
        select(ClinicalNote)
        .options(selectinload(ClinicalNote.provider))
        .join(Patient, Patient.id == ClinicalNote.patient_id)
        .where(
            ClinicalNote.id == note_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _apply_update(note: ClinicalNote, data: dict) -> None:
    """Apply a partial update, remapping the wire `type` to the note_type column."""
    if "type" in data:
        note.note_type = NoteType(data.pop("type"))
    for field in (
        "content",
        "subjective",
        "objective",
        "assessment",
        "plan",
        "attachments",
        "signed_at",
        "signed_by",
        "provider_id",
        "appointment_id",
    ):
        if field in data:
            setattr(note, field, data[field])
@router.get("/{note_id}", response_model=ClinicalNoteResponse)
async def get_note(
    note_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ClinicalNoteResponse:
    """Get a single clinical note (tenant-scoped)."""
    note = await _get_note_or_404(db, note_id, current_user)
    await log_audit_event(
        db, current_user, "clinical_note_viewed", "clinical_note", note.id, request
    )
    await db.commit()
    return _to_response(note)


@router.post("", response_model=ClinicalNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    request: Request,
    note_data: ClinicalNoteCreate,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ClinicalNoteResponse:
    """Create a clinical note for a patient in the caller's practice."""
    await _get_patient_or_404(db, note_data.patient_id, current_user)

    provider_id = note_data.provider_id or current_user.id
    await _validate_note_references(
        db,
        current_user,
        patient_id=note_data.patient_id,
        provider_id=note_data.provider_id,
        appointment_id=note_data.appointment_id,
    )
    note = ClinicalNote(
        patient_id=note_data.patient_id,
        provider_id=provider_id,
        appointment_id=note_data.appointment_id,
        note_type=NoteType(note_data.type),
        content=note_data.content,
        subjective=note_data.subjective,
        objective=note_data.objective,
        assessment=note_data.assessment,
        plan=note_data.plan,
        attachments=note_data.attachments or [],
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    # provider is the creator on create; compute the name directly so we don't
    # need to re-join the relationship after commit.
    provider_name = (
        f"{current_user.first_name} {current_user.last_name}".strip()
        if provider_id == current_user.id
        else ""
    )
    await log_audit_event(
        db, current_user, "clinical_note_created", "clinical_note", note.id, request
    )
    await db.commit()
    return _to_response(note, provider_name=provider_name)


@router.put("/{note_id}", response_model=ClinicalNoteResponse)
async def update_note(
    note_id: UUID,
    request: Request,
    note_data: ClinicalNoteUpdate,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ClinicalNoteResponse:
    """Partially update a clinical note (tenant-scoped)."""
    note = await _get_note_or_404(db, note_id, current_user)
    data = note_data.model_dump(exclude_unset=True)
    # H-05 FIX: updates accepted the same unvalidated provider_id /
    # appointment_id as create did.
    await _validate_note_references(
        db,
        current_user,
        patient_id=note.patient_id,
        provider_id=data.get("provider_id"),
        appointment_id=data.get("appointment_id"),
    )
    _apply_update(note, data)
    await db.commit()
    await db.refresh(note)
    await log_audit_event(
        db, current_user, "clinical_note_updated", "clinical_note", note.id, request
    )
    await db.commit()
    return _to_response(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(*CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> None:
    """Delete a clinical note (tenant-scoped). Returns 204."""
    note = await _get_note_or_404(db, note_id, current_user)
    await log_audit_event(
        db, current_user, "clinical_note_deleted", "clinical_note", note.id, request
    )
    await db.delete(note)
    await db.commit()
    return None