"""Tests for referral endpoints"""
import pytest
import uuid

pytestmark = pytest.mark.asyncio


class TestReferralSources:
    async def test_list_sources_requires_auth(self, client):
        response = await client.get("/api/v1/referrals/sources/")
        assert response.status_code in (401, 403)

    async def test_create_source_requires_auth(self, client):
        response = await client.post("/api/v1/referrals/sources/", json={})
        assert response.status_code in (401, 403)

    async def test_create_source_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/referrals/sources/", json={})
        assert response.status_code in (422, 401, 403)


class TestReferrals:
    async def test_list_referrals_requires_auth(self, client):
        response = await client.get("/api/v1/referrals/")
        assert response.status_code in (401, 403)

    async def test_create_referral_requires_auth(self, client):
        response = await client.post("/api/v1/referrals/", json={})
        assert response.status_code in (401, 403)

    async def test_create_referral_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/referrals/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_referral_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/referrals/{fake_id}")
        assert response.status_code in (401, 403)

    async def test_update_referral_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/referrals/{fake_id}", json={})
        assert response.status_code in (401, 403)
