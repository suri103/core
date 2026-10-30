"""Tests for chair / appointment-type write endpoints.

These cover the previously-missing create/update/delete routes for scheduling
config (chairs and appointment types) and lock them behind OWNER/ADMIN.
"""
import uuid

import pytest
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio


def _dentist_headers(client, db_session, test_practice):
    """Create a DENTIST user (in the same test practice) and mint a token."""
    user = User(
        id=uuid.uuid4(),
        email=f"dentist_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("testpassword123"),
        first_name="Doc",
        last_name="Dentist",
        role=UserRole.DENTIST,
        practice_id=test_practice.id,
        is_active=True,
    )
    db_session.add(user)
    return user


async def _login_dentist(client, db_session, test_practice):
    user = _dentist_headers(client, db_session, test_practice)
    await db_session.flush()
    await db_session.refresh(user)
    token = create_access_token(
        {
            "sub": str(user.id),
            "type": "access",
            "role": "DENTIST",
            "practice_id": str(user.practice_id),
        }
    )
    return {"Authorization": f"Bearer {token}"}


class TestChairWrite:
    async def test_create_chair_requires_auth(self, client):
        resp = await client.post("/api/v1/chairs", json={"name": "Op 1"})
        assert resp.status_code in (401, 403)

    async def test_create_and_list_chair(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/chairs", json={"name": "Op 1", "color": "#123456"}, headers=auth_headers
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Op 1"
        assert body["color"] == "#123456"
        assert body["is_active"] is True

        listed = await client.get("/api/v1/chairs", headers=auth_headers)
        assert body["id"] in [c["id"] for c in listed.json()]

    async def test_update_chair(self, client, auth_headers):
        created = await client.post("/api/v1/chairs", json={"name": "Op 2"}, headers=auth_headers)
        cid = created.json()["id"]
        upd = await client.put(
            f"/api/v1/chairs/{cid}",
            json={"name": "Renamed", "is_active": False},
            headers=auth_headers,
        )
        assert upd.status_code == 200
        assert upd.json()["name"] == "Renamed"
        assert upd.json()["is_active"] is False

    async def test_delete_chair_soft(self, client, auth_headers):
        created = await client.post("/api/v1/chairs", json={"name": "Op 3"}, headers=auth_headers)
        cid = created.json()["id"]
        deleted = await client.delete(f"/api/v1/chairs/{cid}", headers=auth_headers)
        assert deleted.status_code == 204
        listed = await client.get("/api/v1/chairs", headers=auth_headers)
        chairs = [c for c in listed.json() if c["id"] == cid]
        # Soft delete: the chair still exists but is marked inactive.
        assert chairs and chairs[0]["is_active"] is False

    async def test_create_chair_rejects_dentist(self, client, db_session, test_practice):
        headers = await _login_dentist(client, db_session, test_practice)
        resp = await client.post("/api/v1/chairs", json={"name": "x"}, headers=headers)
        assert resp.status_code == 403


class TestAppointmentTypeWrite:
    async def test_create_and_list_type(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/appointment-types",
            json={"name": "Consult", "duration": 30, "color": "#ABCDEF"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Consult"

        listed = await client.get("/api/v1/appointment-types", headers=auth_headers)
        assert resp.json()["id"] in [t["id"] for t in listed.json()]

    async def test_update_type(self, client, auth_headers):
        created = await client.post(
            "/api/v1/appointment-types",
            json={"name": "Fill", "duration": 45, "color": "#000000"},
            headers=auth_headers,
        )
        tid = created.json()["id"]
        upd = await client.put(
            f"/api/v1/appointment-types/{tid}",
            json={"duration": 60, "is_active": False},
            headers=auth_headers,
        )
        assert upd.status_code == 200
        assert upd.json()["duration"] == 60
        assert upd.json()["is_active"] is False

    async def test_delete_type(self, client, auth_headers):
        created = await client.post(
            "/api/v1/appointment-types",
            json={"name": "Extr", "duration": 45, "color": "#111111"},
            headers=auth_headers,
        )
        tid = created.json()["id"]
        deleted = await client.delete(f"/api/v1/appointment-types/{tid}", headers=auth_headers)
        assert deleted.status_code == 204

    async def test_create_type_rejects_dentist(self, client, db_session, test_practice):
        headers = await _login_dentist(client, db_session, test_practice)
        resp = await client.post(
            "/api/v1/appointment-types",
            json={"name": "x", "duration": 30, "color": "#000000"},
            headers=headers,
        )
        assert resp.status_code == 403
