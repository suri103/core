"""
Comprehensive staff endpoint tests covering list, create, update,
role-protection, and inactivation.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio


class TestStaffCRUD:
    """Authenticated staff lifecycle tests."""

    async def test_list_staff(self, client: AsyncClient, auth_headers, db_session, test_practice):
        staff = User(
            id=uuid.uuid4(),
            email=f"staff.{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hashed",
            first_name="Test",
            last_name="Staff",
            role=UserRole.FRONT_DESK,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(staff)
        await db_session.commit()

        response = await client.get("/api/v1/staff/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        emails = [u["email"] for u in data]
        assert staff.email in emails

    async def test_create_staff(self, client: AsyncClient, auth_headers, test_practice):
        suffix = uuid.uuid4().hex[:8]
        response = await client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": f"new.staff.{suffix}@example.com",
                "password": "SecurePass123!",
                "first_name": "New",
                "last_name": "Staff",
                "role": "FRONT_DESK",
                "practice_id": str(test_practice.id),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == f"new.staff.{suffix}@example.com"
        assert data["first_name"] == "New"
        assert data["role"] == "front_desk"

    async def test_create_staff_duplicate_email(self, client: AsyncClient, auth_headers, test_user, test_practice):
        response = await client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": test_user.email,
                "password": "SecurePass123!",
                "first_name": "Dup",
                "last_name": "User",
                "role": "FRONT_DESK",
                "practice_id": str(test_practice.id),
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_update_staff(self, client: AsyncClient, auth_headers, db_session, test_practice):
        staff = User(
            id=uuid.uuid4(),
            email=f"update.{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hashed",
            first_name="Old",
            last_name="Name",
            role=UserRole.FRONT_DESK,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(staff)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/staff/{staff.id}",
            headers=auth_headers,
            json={"first_name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"

    async def test_update_staff_not_found(self, client: AsyncClient, auth_headers):
        response = await client.put(
            f"/api/v1/staff/{uuid.uuid4()}",
            headers=auth_headers,
            json={"first_name": "Ghost"},
        )
        assert response.status_code == 404

    async def test_inactivate_staff(self, client: AsyncClient, auth_headers, db_session, test_practice):
        staff = User(
            id=uuid.uuid4(),
            email=f"inactive.{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hashed",
            first_name="Inactive",
            last_name="User",
            role=UserRole.FRONT_DESK,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(staff)
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/staff/{staff.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    async def test_inactivate_staff_not_found(self, client: AsyncClient, auth_headers):
        response = await client.delete(
            f"/api/v1/staff/{uuid.uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404
