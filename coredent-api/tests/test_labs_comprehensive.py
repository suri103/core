"""
Comprehensive labs endpoint tests.
"""
import pytest
from httpx import AsyncClient

from app.models.lab import Lab, LabCase, LabCaseStatus, LabCaseType

pytestmark = pytest.mark.asyncio


class TestLabCaseEndpoints:
    """Lab case CRUD tests."""

    async def test_list_lab_cases(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient, test_user):
        lab = Lab(
            practice_id=test_practice.id,
            name="Dental Lab Inc",
            contact_name="Lab Contact",
            email="lab@example.com",
            phone="555-1234",
            is_active=True,
        )
        db_session.add(lab)
        await db_session.flush()

        case = LabCase(
            practice_id=test_practice.id,
            lab_id=lab.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            case_number="CASE-001",
            case_type=LabCaseType.CROWN,
            status=LabCaseStatus.PENDING,
        )
        db_session.add(case)
        await db_session.commit()

        response = await client.get("/api/v1/labs/cases/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

    async def test_get_lab_case(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient, test_user):
        lab = Lab(
            practice_id=test_practice.id,
            name="Smile Lab",
            contact_name="Contact",
            email="smile@example.com",
            phone="555-5678",
            is_active=True,
        )
        db_session.add(lab)
        await db_session.flush()

        case = LabCase(
            practice_id=test_practice.id,
            lab_id=lab.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            case_number="CASE-002",
            case_type=LabCaseType.BRIDGE,
            status=LabCaseStatus.SENT,
        )
        db_session.add(case)
        await db_session.commit()

        response = await client.get(f"/api/v1/labs/cases/{case.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(case.id)
        assert data["case_number"] == "CASE-002"

    async def test_get_lab_case_not_found(self, client: AsyncClient, auth_headers):
        import uuid
        response = await client.get(f"/api/v1/labs/cases/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    async def test_create_lab_case(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient, test_user):
        lab = Lab(
            practice_id=test_practice.id,
            name="Create Lab",
            contact_name="Contact",
            email="create@example.com",
            phone="555-9999",
            is_active=True,
        )
        db_session.add(lab)
        await db_session.commit()

        response = await client.post(
            "/api/v1/labs/cases/",
            headers=auth_headers,
            json={
                "lab_id": str(lab.id),
                "patient_id": str(test_patient.id),
                "case_type": "crown",
                "description": "Crown for molar",
                "teeth_involved": "14",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["case_type"] == "crown"
        assert data["description"] == "Crown for molar"

    async def test_create_lab_case_patient_not_found(self, client: AsyncClient, auth_headers, db_session, test_practice, test_user):
        lab = Lab(
            practice_id=test_practice.id,
            name="Missing Patient Lab",
            contact_name="Contact",
            email="missing@example.com",
            phone="555-0000",
            is_active=True,
        )
        db_session.add(lab)
        await db_session.commit()

        import uuid
        response = await client.post(
            "/api/v1/labs/cases/",
            headers=auth_headers,
            json={
                "lab_id": str(lab.id),
                "patient_id": str(uuid.uuid4()),
                "case_type": "crown",
            },
        )
        assert response.status_code == 404

    async def test_delete_lab_case(self, client: AsyncClient, auth_headers, db_session, test_practice, test_patient, test_user):
        lab = Lab(
            practice_id=test_practice.id,
            name="Delete Lab",
            contact_name="Contact",
            email="delete@example.com",
            phone="555-1111",
            is_active=True,
        )
        db_session.add(lab)
        await db_session.flush()

        case = LabCase(
            practice_id=test_practice.id,
            lab_id=lab.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            case_number="CASE-DEL",
            case_type=LabCaseType.BRIDGE,
            status=LabCaseStatus.PENDING,
        )
        db_session.add(case)
        await db_session.commit()

        response = await client.delete(f"/api/v1/labs/cases/{case.id}", headers=auth_headers)
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()
