"""
Documents and Digital Intake Forms API
Manages document templates, patient forms, and e-signatures
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_practice_id, verify_csrf
from app.core.audit import log_audit_event
from app.models.user import User
from app.models.patient import Patient
from app.models.document import (
    Document,
    DocumentTemplate,
    DocumentStatus,
)

router = APIRouter()


# ── Templates ─────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
):
    """List document templates (intake forms, consents, etc)"""
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.practice_id == practice_id)
    )
    templates = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "type": t.category.value if hasattr(t.category, "value") else str(t.category),
            "lastUpdated": t.updated_at.strftime("%b %d, %Y") if t.updated_at else None,
            "usage": t.times_used or 0,
        }
        for t in templates
    ]


# ── Documents (Forms) ──────────────────────────────────────────────────

@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    practice_id: UUID = Depends(get_current_practice_id),
    current_user: User = Depends(get_current_user),
):
    """List patient documents"""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Document)
        .where(Document.practice_id == practice_id)
        .options(selectinload(Document.patient))
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "name": d.name,
            "patient": (
                f"{d.patient.first_name} {d.patient.last_name}" if d.patient else "Unknown"
            ),
            "type": d.category.value if hasattr(d.category, "value") else str(d.category),
            "status": (
                "Signed"
                if d.is_completed
                else ("Pending Signature" if d.status == DocumentStatus.PENDING else "Draft")
            ),
            "date": d.created_at.strftime("%b %d, %Y") if d.created_at else None,
        }
        for d in docs
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_document(
    patient_id: UUID,
    template_id: UUID,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    practice_id: UUID = Depends(get_current_practice_id),
    _csrf: bool = Depends(verify_csrf),
):
    """Assign a form template to a patient"""
    # Load template scoped to practice
    template_result = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.practice_id == practice_id,
        )
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Verify patient belongs to this practice
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        )
    )
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    doc = Document(
        practice_id=practice_id,
        patient_id=patient_id,
        template_id=template_id,
        created_by=current_user.id,
        name=template.name,
        category=template.category,
        content=template.template_content,
        status=DocumentStatus.PENDING,
        is_completed=False,
    )
    db.add(doc)

    # H-02 FIX: Atomic increment to avoid read-modify-write lost updates
    await db.execute(
        update(DocumentTemplate)
        .where(DocumentTemplate.id == template_id)
        .values(times_used=func.coalesce(DocumentTemplate.times_used, 0) + 1)
    )

    # H-03 FIX: Audit Logging for patient document assignment
    await log_audit_event(
        db,
        current_user,
        "document_assigned",
        "document",
        doc.id,
        request,
        changes={
            "patient_id": str(patient_id),
            "template_id": str(template_id),
            "name": template.name,
        },
    )

    await db.commit()
    await db.refresh(doc)
    return {"status": "success", "id": str(doc.id)}
