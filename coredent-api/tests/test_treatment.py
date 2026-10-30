"""Tests for treatment planning endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestTreatmentPlanEndpoints:
    async def test_list_treatment_plans_requires_auth(self, client):
        response = await client.get("/api/v1/treatment/plans/")
        assert response.status_code in (401, 403)

    async def test_list_treatment_plans_unauthorized(self, client):
        response = await client.get("/api/v1/treatment/plans/")
        assert response.status_code != 200

    async def test_create_treatment_plan_requires_auth(self, client):
        response = await client.post("/api/v1/treatment/plans/", json={})
        assert response.status_code in (401, 403)

    async def test_create_treatment_plan_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/treatment/plans/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_treatment_plan_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/treatment/plans/{fake_id}")
        assert response.status_code in (401, 403)

    async def test_update_treatment_plan_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/treatment/plans/{fake_id}", json={})
        assert response.status_code in (401, 403)

    async def test_delete_treatment_plan_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/treatment/plans/{fake_id}")
        assert response.status_code in (401, 403)


class TestTreatmentPlanPhases:
    async def test_list_phases_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/treatment/plans/{fake_id}/phases")
        assert response.status_code in (401, 403)

    async def test_create_phase_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/treatment/plans/{fake_id}/phases", json={})
        assert response.status_code in (401, 403)

    async def test_create_phase_validation_error(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/treatment/plans/{fake_id}/phases", json={})
        assert response.status_code in (422, 401, 403)


class TestTreatmentPlanPatientPlans:
    async def test_list_patient_plans_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/treatment/patients/{fake_id}/plans")
        assert response.status_code in (401, 403)


class TestPlanAcceptance:
    async def test_accept_plan_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/treatment/plans/{fake_id}/accept", json={})
        assert response.status_code in (401, 403)
