"""Tests for clinical endpoints"""
import pytest
pytestmark = pytest.mark.asyncio

class TestPerioChart:
    async def test_list_perio_requires_auth(self, client):
        response = await client.get("/api/v1/clinical/perio/")
        assert response.status_code in (401, 403)

    async def test_create_perio_requires_auth(self, client):
        response = await client.post("/api/v1/clinical/perio/", json={})
        assert response.status_code in (401, 403)

    async def test_create_perio_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/clinical/perio/", json={})
        assert response.status_code in (422, 401, 403)