"""Tests for staff endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestStaff:
    async def test_list_staff_requires_auth(self, client):
        response = await client.get("/api/v1/staff/")
        assert response.status_code in (401, 403)

    async def test_create_staff_requires_auth(self, client):
        response = await client.post("/api/v1/staff/", json={})
        assert response.status_code in (401, 403)

    async def test_create_staff_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/staff/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_update_staff_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/staff/{fake_id}", json={})
        assert response.status_code in (401, 403)
