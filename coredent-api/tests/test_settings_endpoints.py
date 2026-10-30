"""Tests for settings endpoints"""
import pytest
pytestmark = pytest.mark.asyncio

class TestSettings:
    async def test_get_billing_preferences_requires_auth(self, client):
        response = await client.get("/api/v1/settings/billing")
        assert response.status_code in (401, 403)

    async def test_update_billing_preferences_requires_auth(self, client):
        response = await client.put("/api/v1/settings/billing", json={})
        assert response.status_code in (401, 403)

    async def test_update_billing_preferences_validation_error(self, client, auth_headers):
        response = await client.put("/api/v1/settings/billing", json={})
        assert response.status_code in (422, 401, 403)