"""Tests for first-login forced password change + staff invitation flow.

Covers:
- create_staff sets must_change_password=True on admin-provisioned accounts
- login reports must_change_password
- the API gate blocks everything but the password-change flow while armed
- /auth/change-password clears the flag and unlocks the account
- /staff/invitations CRUD + role-escalation guard
- /auth/invitations/validate + /accept end-to-end
"""
import uuid as uuid_lib

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.staff_invitation import StaffInvitation
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio


def _staff_payload(email_suffix: str, practice_id, role: str = "FRONT_DESK") -> dict:
    return {
        "email": f"gate.{uuid_lib.uuid4().hex[:8]}.{email_suffix}@example.com",
        "password": "TempPass123!",
        "first_name": "Temp",
        "last_name": "Staff",
        "role": role,
        "practice_id": str(practice_id),
    }


async def _create_user(db_session, practice, *, role=UserRole.DENTIST, must_change=False):
    email = f"user.{uuid_lib.uuid4().hex[:8]}@example.com"
    user = User(
        id=uuid_lib.uuid4(),
        email=email,
        password_hash=get_password_hash("TempPass123!"),
        first_name="Gate",
        last_name="User",
        role=role,
        practice_id=practice.id,
        is_active=True,
        is_email_verified=True,
        must_change_password=must_change,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, user) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TempPass123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


class TestMustChangePassword:
    async def test_create_staff_sets_flag(self, client: AsyncClient, auth_headers, test_practice):
        payload = _staff_payload("created", test_practice.id)
        response = await client.post(
            "/api/v1/staff/", headers=auth_headers, json=payload
        )
        assert response.status_code == 201
        assert response.json()["must_change_password"] is True

    async def test_login_reports_flag(self, client: AsyncClient, db_session, test_practice):
        user = await _create_user(db_session, test_practice, must_change=True)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TempPass123!"},
        )
        assert response.status_code == 200
        assert response.json()["must_change_password"] is True

    async def test_gate_blocks_everything_but_password_change(
        self, client: AsyncClient, db_session, test_practice
    ):
        user = await _create_user(db_session, test_practice, must_change=True)
        token = await _login(client, user)
        headers = {"Authorization": f"Bearer {token}"}

        # Profile read and CSRF bootstrap stay reachable (UI needs them to
        # render the force-change screen).
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["must_change_password"] is True

        # PHI endpoints are closed while armed.
        patients = await client.get("/api/v1/patients", headers=headers)
        assert patients.status_code == 403

    async def test_change_password_clears_flag_and_unlocks(
        self, client: AsyncClient, auth_headers, db_session, test_practice
    ):
        user = await _create_user(db_session, test_practice, must_change=True)
        token = await _login(client, user)
        csrf = await client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf.json()["csrf_token"],
        }

        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "TempPass123!",
                "new_password": "NewSecure456!",
            },
        )
        assert response.status_code == 200, response.text

        # Login with the rotated password: flag cleared, endpoints unlocked.
        relogin = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "NewSecure456!"},
        )
        assert relogin.status_code == 200
        assert relogin.json()["must_change_password"] is False

        new_token = relogin.json()["access_token"]
        unlocked = await client.get(
            "/api/v1/patients", headers={"Authorization": f"Bearer {new_token}"}
        )
        assert unlocked.status_code == 200

    async def test_admin_password_reset_rearms_flag(
        self, client: AsyncClient, auth_headers, db_session, test_practice
    ):
        user = await _create_user(db_session, test_practice, must_change=False)

        response = await client.put(
            f"/api/v1/staff/{user.id}",
            headers=auth_headers,
            json={"password": "ResetTemp123!"},
        )
        assert response.status_code == 200
        assert response.json()["must_change_password"] is True


class TestStaffInvitations:
    async def test_create_invite_flow(self, client: AsyncClient, auth_headers):
        payload = {
            "email": f"invite.{uuid_lib.uuid4().hex[:8]}@example.com",
            "first_name": "Dana",
            "last_name": "Dentist",
            "role": "dentist",
        }
        create = await client.post(
            "/api/v1/staff/invitations", headers=auth_headers, json=payload
        )
        assert create.status_code == 201, create.text
        data = create.json()
        assert data["email"] == payload["email"]
        assert data["role"] == "dentist"

        listing = await client.get("/api/v1/staff/invitations", headers=auth_headers)
        assert listing.status_code == 200
        assert any(i["email"] == payload["email"] for i in listing.json())

    async def test_duplicate_invite_rejected(self, client: AsyncClient, auth_headers):
        payload = {
            "email": f"dup.{uuid_lib.uuid4().hex[:8]}@example.com",
            "first_name": "Dup",
            "last_name": "Invite",
            "role": "front_desk",
        }
        first = await client.post(
            "/api/v1/staff/invitations", headers=auth_headers, json=payload
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/v1/staff/invitations", headers=auth_headers, json=payload
        )
        assert second.status_code == 409

    async def test_admin_cannot_invite_owner(self, client: AsyncClient, db_session, test_practice):
        admin = await _create_user(db_session, test_practice, role=UserRole.ADMIN)
        token = await _login(client, admin)
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "email": f"owner.{uuid_lib.uuid4().hex[:8]}@example.com",
            "first_name": "Sneaky",
            "last_name": "Owner",
            "role": "owner",
        }
        response = await client.post(
            "/api/v1/staff/invitations", headers=headers, json=payload
        )
        # Escalation guard mirrors create_staff: admins cannot mint owners.
        assert response.status_code == 403

    async def test_cancel_invitation(self, client: AsyncClient, auth_headers):
        payload = {
            "email": f"cancel.{uuid_lib.uuid4().hex[:8]}@example.com",
            "first_name": "Cancel",
            "last_name": "Me",
            "role": "hygienist",
        }
        create = await client.post(
            "/api/v1/staff/invitations", headers=auth_headers, json=payload
        )
        invitation_id = create.json()["id"]

        cancel = await client.delete(
            f"/api/v1/staff/invitations/{invitation_id}", headers=auth_headers
        )
        assert cancel.status_code == 200

        listing = await client.get("/api/v1/staff/invitations", headers=auth_headers)
        assert invitation_id not in [i["id"] for i in listing.json()]

    async def test_validate_and_accept_invitation_end_to_end(
        self, client: AsyncClient, auth_headers, db_session, test_practice
    ):
        from app.core.security import generate_password_reset_token, hash_token

        email = f"accept.{uuid_lib.uuid4().hex[:8]}@example.com"
        token = generate_password_reset_token()
        invitation = StaffInvitation(
            practice_id=test_practice.id,
            email=email,
            first_name="Accepted",
            last_name="Invitee",
            role=UserRole.DENTIST,
            token_hash=hash_token(token),
            expires_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ) + __import__("datetime").timedelta(hours=72),
        )
        db_session.add(invitation)
        await db_session.commit()

        validate = await client.post(
            "/api/v1/auth/invitations/validate", json={"token": token}
        )
        assert validate.status_code == 200
        body = validate.json()
        assert body["isValid"] is True
        assert body["email"] == email
        assert body["role"] == "dentist"

        accept = await client.post(
            "/api/v1/auth/invitations/accept",
            json={"token": token, "password": "ChosenPass123!"},
        )
        assert accept.status_code == 200, accept.text

        # M1 FIX: the invitation link is not proof of inbox ownership, so the
        # account starts UNVERIFIED — login is refused until the emailed
        # verification link is confirmed. H-7 (anti-enumeration) collapses all
        # post-lookup login failures to a uniform 401, so the pre-verification
        # refusal surfaces as 401 with the same generic detail as a wrong
        # password.
        pre_verify_login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "ChosenPass123!"},
        )
        assert pre_verify_login.status_code == 401
        assert pre_verify_login.json()["detail"] == "Incorrect email or password"

        # The emailed verification link flips the same flag the accept
        # response cannot reveal (the token is hashed at rest).
        from sqlalchemy import select

        from app.models.user import User as UserModel

        invitee = (
            await db_session.execute(
                select(UserModel).where(UserModel.email == email)
            )
        ).scalar_one()
        invitee.is_email_verified = True
        await db_session.commit()

        # The account now exists and can sign in with the chosen password.
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "ChosenPass123!"},
        )
        assert login.status_code == 200
        # Self-chosen password: no forced rotation needed.
        assert login.json()["must_change_password"] is False

    async def test_validate_rejects_expired_or_used_token(
        self, client: AsyncClient, db_session, test_practice
    ):
        from datetime import datetime, timedelta, timezone
        from app.core.security import generate_password_reset_token, hash_token

        expired_token = generate_password_reset_token()
        invitation = StaffInvitation(
            practice_id=test_practice.id,
            email="expired@example.com",
            first_name="Old",
            last_name="Invite",
            role=UserRole.DENTIST,
            token_hash=hash_token(expired_token),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(invitation)
        await db_session.commit()

        validate = await client.post(
            "/api/v1/auth/invitations/validate", json={"token": expired_token}
        )
        assert validate.json()["isValid"] is False

        bad_token = "not-a-real-token"
        accept = await client.post(
            "/api/v1/auth/invitations/accept",
            json={"token": bad_token, "password": "ChosenPass123!"},
        )
        assert accept.status_code == 400
