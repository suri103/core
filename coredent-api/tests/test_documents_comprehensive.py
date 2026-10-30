"""
Comprehensive documents endpoint tests.
"""
import pytest
from httpx import AsyncClient

from app.models.document import DocumentTemplate, DocumentCategory, DocumentStatus, Document

pytestmark = pytest.mark.asyncio


class TestDocumentTemplates:
    """Document template endpoint tests."""

    async def test_list_templates(self, client: AsyncClient, auth_headers, db_session, test_practice):
        template = DocumentTemplate(
            practice_id=test_practice.id,
            name="Consent Form",
            category=DocumentCategory.CONSENT,
            template_content="<p>I consent to treatment.</p>",
        )
        db_session.add(template)
        await db_session.commit()

        response = await client.get("/api/v1/documents/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(t["name"] == "Consent Form" for t in data)


class TestDocuments:
    """Document endpoint tests."""

    async def test_list_documents(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient):
        template = DocumentTemplate(
            practice_id=test_practice.id,
            name="Financial Policy",
            category=DocumentCategory.FINANCIAL,
            template_content="<p>Payment terms...</p>",
        )
        db_session.add(template)
        await db_session.flush()

        doc = Document(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            template_id=template.id,
            name="Financial Policy",
            category=DocumentCategory.FINANCIAL,
            content="<p>Payment terms...</p>",
            status=DocumentStatus.PENDING,
            is_completed=False,
        )
        db_session.add(doc)
        await db_session.commit()

        response = await client.get("/api/v1/documents/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(d["name"] == "Financial Policy" for d in data)

    async def test_create_document(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient):
        template = DocumentTemplate(
            practice_id=test_practice.id,
            name="HIPAA Consent",
            category=DocumentCategory.CONSENT,
            template_content="<p>HIPAA notice...</p>",
        )
        db_session.add(template)
        await db_session.commit()

        response = await client.post(
            "/api/v1/documents/",
            headers=auth_headers,
            params={"patient_id": str(test_patient.id), "template_id": str(template.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "id" in data

    async def test_create_document_template_not_found(self, client: AsyncClient, auth_headers, test_patient):
        import uuid
        response = await client.post(
            "/api/v1/documents/",
            headers=auth_headers,
            params={"patient_id": str(test_patient.id), "template_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    async def test_create_document_patient_not_found(self, client: AsyncClient, auth_headers, db_session, test_practice):
        import uuid
        template = DocumentTemplate(
            practice_id=test_practice.id,
            name="Missing Patient Template",
            category=DocumentCategory.OTHER,
            template_content="<p>...</p>",
        )
        db_session.add(template)
        await db_session.commit()

        response = await client.post(
            "/api/v1/documents/",
            headers=auth_headers,
            params={"patient_id": str(uuid.uuid4()), "template_id": str(template.id)},
        )
        assert response.status_code == 404
