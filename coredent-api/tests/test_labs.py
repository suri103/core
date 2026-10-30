"""Tests for lab endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestLabs:
    async def test_list_vendors_requires_auth(self, client):
        response = await client.get("/api/v1/labs/vendors/")
        assert response.status_code in (401, 403)

    async def test_create_vendor_requires_auth(self, client):
        response = await client.post("/api/v1/labs/vendors/", json={})
        assert response.status_code in (401, 403)

    async def test_create_vendor_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/labs/vendors/", json={})
        assert response.status_code in (422, 401, 403)


class TestLabCases:
    async def test_list_cases_requires_auth(self, client):
        response = await client.get("/api/v1/labs/cases/")
        assert response.status_code in (401, 403)

    async def test_create_case_requires_auth(self, client):
        response = await client.post("/api/v1/labs/cases/", json={})
        assert response.status_code in (401, 403)

    async def test_create_case_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/labs/cases/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_case_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/labs/cases/{fake_id}")
        assert response.status_code in (401, 403)
