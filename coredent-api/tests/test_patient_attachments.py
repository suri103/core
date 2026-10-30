import io
import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.models.user import UserRole
from app.models.patient import Patient, PatientStatus


PDF_CONTENT = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\nxref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n100\n%%EOF"


@pytest.mark.asyncio
class TestPatientAttachments:
    async def test_upload_list_and_delete_attachment(
        self, client: AsyncClient, test_user, test_patient, auth_headers
    ):
        # 1. Upload attachment
        files = {
            "file": ("consent_form.pdf", io.BytesIO(PDF_CONTENT), "application/pdf")
        }
        data = {"category": "consent"}

        resp = await client.post(
            f"/api/v1/patients/{test_patient.id}/attachments",
            files=files,
            data=data,
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        upload_data = resp.json()
        assert upload_data["name"] == "consent_form.pdf"
        assert upload_data["category"] == "consent"
        assert upload_data["type"] == "application/pdf"
        assert upload_data["size"] == len(PDF_CONTENT)
        attachment_id = upload_data["id"]

        # 2. List attachments
        resp_list = await client.get(
            f"/api/v1/patients/{test_patient.id}/attachments",
            headers=auth_headers,
        )
        assert resp_list.status_code == 200
        items = resp_list.json()
        assert len(items) == 1
        assert items[0]["id"] == attachment_id
        assert items[0]["name"] == "consent_form.pdf"

        # 3. Verify get_patient also returns attachments
        resp_patient = await client.get(
            f"/api/v1/patients/{test_patient.id}",
            headers=auth_headers,
        )
        assert resp_patient.status_code == 200
        patient_data = resp_patient.json()
        assert "attachments" in patient_data
        assert len(patient_data["attachments"]) == 1
        assert str(patient_data["attachments"][0]["id"]) == str(attachment_id)

        # 4. Delete attachment
        resp_del = await client.delete(
            f"/api/v1/patients/{test_patient.id}/attachments/{attachment_id}",
            headers=auth_headers,
        )
        assert resp_del.status_code == 200
        assert resp_del.json()["success"] is True

        # 5. Verify list is now empty
        resp_list2 = await client.get(
            f"/api/v1/patients/{test_patient.id}/attachments",
            headers=auth_headers,
        )
        assert resp_list2.status_code == 200
        assert len(resp_list2.json()) == 0

    async def test_attachment_rejects_fake_extension(
        self, client: AsyncClient, test_user, test_patient, auth_headers
    ):
        # A file with .pdf extension but executable content
        fake_content = b"MZ\x90\x00\x03\x00\x00\x00"
        files = {
            "file": ("malicious.pdf", io.BytesIO(fake_content), "application/pdf")
        }
        resp = await client.post(
            f"/api/v1/patients/{test_patient.id}/attachments",
            files=files,
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "validation failed" in resp.text.lower()
