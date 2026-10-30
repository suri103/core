"""Regression tests for document assignment audit logging and usage counter."""
import uuid
from datetime import date
import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.api.v1.endpoints import documents
from app.models.practice import Practice
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.document import DocumentTemplate, DocumentCategory
from app.models.audit import AuditLog


def _make_request() -> Request:
    return Request(scope={
        "type": "http",
        "client": ("127.0.0.1", 1234),
        "headers": [],
        "path": "/api/v1/documents/",
        "method": "POST",
    })


@pytest.mark.asyncio
async def test_create_document_logs_audit_event_and_increments_usage(db_session):
    practice = Practice(
        id=uuid.uuid4(),
        name="Doc Practice",
        public_slug="doc-practice",
        is_active=True,
    )
    db_session.add(practice)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        practice_id=practice.id,
        email="doctor@example.com",
        password_hash="dummy_hash",
        first_name="Doctor",
        last_name="Audit",
        role=UserRole.DENTIST,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    patient = Patient(
        id=uuid.uuid4(),
        practice_id=practice.id,
        first_name="Alice",
        last_name="Smith",
        date_of_birth=date(1990, 5, 20),
        status="active",
    )
    db_session.add(patient)
    await db_session.flush()

    template = DocumentTemplate(
        id=uuid.uuid4(),
        practice_id=practice.id,
        name="Medical History Form",
        category=DocumentCategory.CONSENT,
        template_content="{}",
        times_used=5,
    )
    db_session.add(template)
    await db_session.commit()

    raw_create = getattr(documents.create_document, "__wrapped__", documents.create_document)
    req = _make_request()

    res = await raw_create(
        patient_id=patient.id,
        template_id=template.id,
        request=req,
        db=db_session,
        current_user=user,
        practice_id=practice.id,
        _csrf=True,
    )
    assert res["status"] == "success"
    doc_id = uuid.UUID(res["id"])

    # 1. Verify audit log entry
    audit_res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "document_assigned",
            AuditLog.entity_id == doc_id,
        )
    )
    audit_entry = audit_res.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.user_id == user.id
    assert audit_entry.changes.get("name") == "Medical History Form"

    # 2. Verify times_used incremented
    await db_session.refresh(template)
    assert template.times_used == 6
