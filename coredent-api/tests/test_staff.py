"""Tests for staff management endpoints (Pydantic validation, RBAC)"""
import uuid

import pytest



class TestStaffPydanticValidation:
    """Verify staff endpoints use Pydantic schemas"""

    async def test_create_staff_rejects_invalid_email(self, async_client, auth_headers, test_practice):
        response = await async_client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": "not-an-email",
                "password": "ValidPass123!",
                "first_name": "Test",
                "last_name": "User",
                "role": "FRONT_DESK",
                "practice_id": str(test_practice.id)
            }
        )
        assert response.status_code == 422

    async def test_create_staff_validates_password_length(self, async_client, auth_headers, test_practice):
        response = await async_client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": "user@example.com",
                "password": "Ab1",  # Only 3 chars, min is 8
                "first_name": "Test",
                "last_name": "User",
                "role": "FRONT_DESK",
                "practice_id": str(test_practice.id)
            }
        )
        assert response.status_code in (422, 400)

    async def test_create_staff_validates_role(self, async_client, auth_headers, test_practice):
        response = await async_client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": "user@example.com",
                "password": "ValidPass123!",
                "first_name": "Test",
                "last_name": "User",
                "role": "invalid_role",
                "practice_id": str(test_practice.id)
            }
        )
        assert response.status_code == 422


class TestStaffListing:
    """Test staff listing permissions"""

    async def test_list_staff_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/staff/")
        assert response.status_code == 401


class TestStaffUpdateSchema:
    """Test staff update uses UserUpdate Pydantic schema"""

    def test_user_update_allows_partial_updates(self):
        from app.schemas.user import UserUpdate
        data = UserUpdate(first_name="NewName")
        assert data.first_name == "NewName"
        assert data.email is None
        assert data.role is None

    def test_user_update_validates_email(self):
        from pydantic import ValidationError
        from app.schemas.user import UserUpdate
        with pytest.raises(ValidationError):
            UserUpdate(email="not-an-email")

    def test_user_update_password_not_exposed(self):
        from app.schemas.user import UserUpdate
        data = UserUpdate()
        assert not hasattr(data, 'password')


class TestPlatformRoleEscalation:
    """A practice-scoped route must never mint a platform SUPER_ADMIN.

    SUPER_ADMIN is the only gate on the cross-tenant /platform/* console, so an
    assignable SUPER_ADMIN turns any practice OWNER/ADMIN into a SaaS operator.
    """

    async def test_create_staff_rejects_super_admin(self, async_client, auth_headers, test_practice):
        response = await async_client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": "escalation@example.com",
                "password": "ValidPass123!",
                "first_name": "Eve",
                "last_name": "Escalation",
                "role": "SUPER_ADMIN",
                "practice_id": str(test_practice.id),
            },
        )
        assert response.status_code == 403
        assert "Platform roles" in response.json()["detail"]

    async def test_update_staff_rejects_super_admin(self, async_client, auth_headers, test_user):
        response = await async_client.put(
            f"/api/v1/staff/{test_user.id}",
            headers=auth_headers,
            json={"role": "SUPER_ADMIN"},
        )
        assert response.status_code == 403
        assert "Platform roles" in response.json()["detail"]

    async def test_invitation_rejects_super_admin(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v1/staff/invitations",
            headers=auth_headers,
            json={
                "email": "invite-escalation@example.com",
                "first_name": "Eve",
                "last_name": "Escalation",
                "role": "SUPER_ADMIN",
            },
        )
        assert response.status_code == 403
        assert "Platform roles" in response.json()["detail"]

    async def test_owner_can_still_assign_practice_roles(self, async_client, auth_headers, test_practice):
        """Positive control: the guard must not block legitimate roles."""
        response = await async_client.post(
            "/api/v1/staff/",
            headers=auth_headers,
            json={
                "email": f"front-desk-{uuid.uuid4().hex[:8]}@example.com",
                "password": "ValidPass123!",
                "first_name": "Front",
                "last_name": "Desk",
                "role": "FRONT_DESK",
                "practice_id": str(test_practice.id),
            },
        )
        assert response.status_code == 201, response.text

    def test_validator_rejects_platform_roles_directly(self):
        from fastapi import HTTPException

        from app.api.v1.endpoints.staff import _validate_practice_role_assignment
        from app.models.user import User, UserRole

        actor = User(role=UserRole.OWNER)
        with pytest.raises(HTTPException) as exc:
            _validate_practice_role_assignment(UserRole.SUPER_ADMIN, actor)
        assert exc.value.status_code == 403
        assert _validate_practice_role_assignment(UserRole.DENTIST, actor) == UserRole.DENTIST