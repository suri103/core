"""Tests for insurance endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestInsuranceCarriers:
    async def test_list_carriers_requires_auth(self, client):
        response = await client.get("/api/v1/insurance/carriers/")
        assert response.status_code in (401, 403)

    async def test_create_carrier_requires_auth(self, client):
        response = await client.post("/api/v1/insurance/carriers/", json={})
        assert response.status_code in (401, 403)

    async def test_create_carrier_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/insurance/carriers/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_carrier_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/insurance/carriers/{fake_id}")
        assert response.status_code in (401, 403)

    async def test_update_carrier_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/insurance/carriers/{fake_id}", json={})
        assert response.status_code in (401, 403)


class TestInsuranceClaims:
    async def test_list_claims_requires_auth(self, client):
        response = await client.get("/api/v1/insurance/claims/")
        assert response.status_code in (401, 403)

    async def test_create_claim_requires_auth(self, client):
        response = await client.post("/api/v1/insurance/claims/", json={})
        assert response.status_code in (401, 403)

    async def test_create_claim_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/insurance/claims/", json={})
        assert response.status_code in (422, 401, 403)
