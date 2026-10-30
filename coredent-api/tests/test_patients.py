"""
Tests for patient endpoints

These tests exercise the real API contract as implemented in
app/api/v1/endpoints/patients.py:
  - Paginated list shape: {items, total, page, limit, pages}
  - Search parameter: ?query=...
  - DELETE returns 204 No Content
  - Duplicate email/phone returns 409 Conflict
"""
import datetime
import uuid as uuid_lib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestPatientEndpoints:
    """Test patient management endpoints"""

    @pytest.mark.asyncio
    async def test_get_patients_success(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """Test getting patients list returns paginated envelope"""
        response = await client.get("/api/v1/patients", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # PaginatedResponse envelope
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "pages" in data
        assert len(data["items"]) >= 1

        # Check patient data structure
        patient = data["items"][0]
        assert "id" in patient
        assert "first_name" in patient
        assert "last_name" in patient
        assert "email" in patient

    @pytest.mark.asyncio
    async def test_get_patients_with_search(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """Test getting patients with search parameter"""
        # Endpoint uses ?query= for search
        response = await client.get(
            "/api/v1/patients?query=Doe", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

        # Should find the test patient
        found = next(
            (p for p in data["items"] if p["first_name"] == "John"),
            None,
        )
        assert found is not None

    @pytest.mark.asyncio
    async def test_get_patients_with_pagination(
        self, client: AsyncClient, auth_headers
    ):
        """Test getting patients with pagination parameters"""
        response = await client.get(
            "/api/v1/patients?page=1&limit=10", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 10

    @pytest.mark.asyncio
    async def test_get_patients_unauthorized(self, client: AsyncClient):
        """Test getting patients without authentication"""
        response = await client.get("/api/v1/patients")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_patient_by_id_success(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """Test getting patient by ID"""
        response = await client.get(
            f"/api/v1/patients/{test_patient.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert str(data["id"]) == str(test_patient.id)
        assert data["first_name"] == test_patient.first_name
        assert data["last_name"] == test_patient.last_name
        assert data["email"] == test_patient.email

    @pytest.mark.asyncio
    async def test_get_patient_by_id_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Non-existent UUID returns 404"""
        missing_id = uuid_lib.uuid4()
        response = await client.get(
            f"/api/v1/patients/{missing_id}", headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_patient_success(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """Test creating a new patient"""
        # Use a random email/phone to avoid collision with the test_patient fixture
        suffix = uuid_lib.uuid4().hex[:8]
        patient_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": f"jane.smith.{suffix}@example.com",
            "phone": f"+1555{suffix[:7]}",
            "date_of_birth": "1985-05-15",
            "gender": "female",
            "address_street": "456 Oak Ave",
            "address_city": "Springfield",
            "address_state": "IL",
            "address_zip": "62702",
            "emergency_contact": {
                "name": "John Smith",
                "relationship": "spouse",
                "phone": "+1987654322",
            },
            "medical_alerts": ["Allergic to penicillin"],
            "status": "active",
        }

        response = await client.post(
            "/api/v1/patients", json=patient_data, headers=auth_headers
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["first_name"] == patient_data["first_name"]
        assert data["last_name"] == patient_data["last_name"]
        assert data["email"] == patient_data["email"]
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_patient_validation_error(
        self, client: AsyncClient, auth_headers
    ):
        """Test creating patient with invalid data rejects at validation"""
        patient_data = {
            "first_name": "",  # Empty name should fail validation
            "email": "invalid-email",  # Invalid email format
        }

        response = await client.post(
            "/api/v1/patients", json=patient_data, headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_patient_duplicate_email(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """Duplicate email or phone in same practice returns 409"""
        patient_data = {
            "first_name": "Another",
            "last_name": "Patient",
            "email": test_patient.email,  # Duplicate email
            "phone": "+1111111111",
            "date_of_birth": "1990-01-01",
            "gender": "male",
        }

        response = await client.post(
            "/api/v1/patients", json=patient_data, headers=auth_headers
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_patient_success(
        self, client: AsyncClient, auth_headers, test_patient, db_session: AsyncSession
    ):
        """Test updating a patient"""
        update_data = {
            "phone": "+1999999999",
            "address_street": "789 Pine St",
            "address_city": "Springfield",
            "address_state": "IL",
            "address_zip": "62703",
        }

        response = await client.put(
            f"/api/v1/patients/{test_patient.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["phone"] == update_data["phone"]
        assert data["address_street"] == update_data["address_street"]
        from app.core.search_index import hmac_index

        await db_session.refresh(test_patient)
        assert test_patient.search_index_phone == hmac_index(update_data["phone"])


    @pytest.mark.asyncio
    async def test_update_patient_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Updating non-existent patient returns 404"""
        missing_id = uuid_lib.uuid4()
        update_data = {"phone": "+1999999999"}

        response = await client.put(
            f"/api/v1/patients/{missing_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_patient_success(
        self,
        client: AsyncClient,
        auth_headers,
        db_session: AsyncSession,
        test_practice,
    ):
        """Delete returns 204 No Content (soft delete to status=inactive)"""
        from app.models.patient import Patient

        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="Delete",
            last_name="Me",
            email=f"delete.me.{uuid_lib.uuid4().hex[:8]}@example.com",
            phone=f"+1{uuid_lib.uuid4().int % 10_000_000_000:010d}",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="male",
            status="active",
        )
        db_session.add(patient)
        await db_session.commit()
        await db_session.refresh(patient)

        response = await client.delete(
            f"/api/v1/patients/{patient.id}", headers=auth_headers
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_patient_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Deleting non-existent patient returns 404"""
        missing_id = uuid_lib.uuid4()
        response = await client.delete(
            f"/api/v1/patients/{missing_id}", headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_patient_data_success(
        self, client: AsyncClient, auth_headers, test_patient, db_session: AsyncSession
    ):
        """Test exporting patient data for GDPR/HIPAA compliance"""
        response = await client.get(
            f"/api/v1/patients/{test_patient.id}/export", headers=auth_headers
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert "exported_at" in data
        assert "exported_by" in data
        assert "patient_demographics" in data
        assert data["patient_demographics"]["id"] == str(test_patient.id)
        assert data["patient_demographics"]["first_name"] == test_patient.first_name
        assert "appointments" in data
        assert "clinical_notes" in data
        assert "treatment_plans" in data

        # Check that audit log was created
        from app.models.audit import AuditLog
        from sqlalchemy import select
        audit_result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "patient_data_exported",
                AuditLog.entity_id == test_patient.id
            )
        )
        audit_log = audit_result.scalar_one_or_none()
        assert audit_log is not None

    @pytest.mark.asyncio
    async def test_anonymize_patient_cascades_child_phi(
        self, client: AsyncClient, auth_headers, test_practice, test_user, db_session: AsyncSession
    ):
        """POST /patients/{id}/anonymize scrubs patient PHI and child free-text records (H5, Decision 7)."""
        from app.models.patient import Patient, PatientStatus, PatientPortalAccessCode
        from app.models.clinical import ClinicalNote, NoteType
        from app.models.appointment import Appointment, AppointmentTypeEnum, AppointmentStatus
        from app.models.portal_lockout import PortalIdentityLockout
        from app.models.document import Document
        from sqlalchemy import select

        patient_email = f"anon.cascade.{uuid_lib.uuid4().hex[:8]}@example.com"
        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="Alice",
            last_name="Smith",
            email=patient_email,
            phone="+15551234567",
            date_of_birth=datetime.date(1985, 5, 20),
            gender="female",
            status=PatientStatus.ACTIVE,
        )
        db_session.add(patient)
        await db_session.flush()

        note = ClinicalNote(
            id=uuid_lib.uuid4(),
            patient_id=patient.id,
            provider_id=test_user.id,
            note_type=NoteType.SOAP,
            content="Sensitive clinical text",
            subjective="Patient complains of excruciating tooth pain",
            plan="Extraction scheduled",
            signed_by="Dr. Test",
        )
        appt = Appointment(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=patient.id,
            appointment_type=AppointmentTypeEnum.CLEANING,
            status=AppointmentStatus.SCHEDULED,
            start_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2, hours=1),
            duration=60,
            notes="Sensitive appointment notes",
            cancellation_reason="None",
        )
        access_code = PatientPortalAccessCode(
            id=uuid_lib.uuid4(),
            patient_id=patient.id,
            practice_id=test_practice.id,
            token_hash="token_hash_for_anonymize_test",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15),
        )
        lockout = PortalIdentityLockout(
            practice_slug=test_practice.public_slug,
            email=patient_email.lower(),
            failed_attempts=3,
        )
        doc = Document(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=patient.id,
            name="Medical History",
            description="Patient medical disclosures",
            content="Sensitive disclosures",
        )
        db_session.add_all([note, appt, access_code, lockout, doc])
        await db_session.commit()

        patient_id = patient.id
        note_id = note.id
        appt_id = appt.id
        access_code_id = access_code.id
        doc_id = doc.id
        practice_slug = test_practice.public_slug

        response = await client.post(
            f"/api/v1/patients/{patient_id}/anonymize", headers=auth_headers
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["first_name"] == "[deleted]"
        assert data["last_name"] == "[deleted]"
        assert data["status"] == "inactive"
        assert data["email"] is None

        # Verify child rows were scrubbed / deleted
        db_session.expire_all()
        get_note = (await db_session.execute(select(ClinicalNote).where(ClinicalNote.id == note_id))).scalar_one()
        assert get_note.content == "[redacted]"
        assert get_note.subjective == "[redacted]"
        assert get_note.signed_by == "[redacted]"

        get_appt = (await db_session.execute(select(Appointment).where(Appointment.id == appt_id))).scalar_one()
        assert get_appt.notes is None
        assert get_appt.cancellation_reason == "[redacted]"
        assert get_appt.status == AppointmentStatus.CANCELLED

        get_doc = (await db_session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert get_doc.content is None
        assert get_doc.description is None

        # Access code and lockout rows must be deleted
        get_code = (await db_session.execute(select(PatientPortalAccessCode).where(PatientPortalAccessCode.id == access_code_id))).scalar_one_or_none()
        assert get_code is None

        get_lockout = (await db_session.execute(select(PortalIdentityLockout).where(
            PortalIdentityLockout.practice_slug == practice_slug,
            PortalIdentityLockout.email == patient_email.lower(),
        ))).scalar_one_or_none()
        assert get_lockout is None

