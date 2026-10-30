"""Tests for plan limit (quota) enforcement.

Covers the production behavior added in ``app/services/plan_quota.py``:

- Patient creation is rejected (403) once ``limits.patients`` is exhausted.
- Staff creation is rejected (403) once ``limits.users`` is exhausted
  (the practice owner who created the user row above already counts as a
  seat, which is standard seat-licensing semantics).
- Creation is allowed while the limit is not yet reached.
- No enforcement when there is no active subscription/plan, no configured
  limit for the dimension, or a negative (unlimited) limit.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SubscriptionInterval,
)


async def _add_active_plan(
    db: AsyncSession,
    practice_id,
    limits: dict,
    name: str = "Quota Plan",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> SubscriptionPlan:
    """Seed an active plan + subscription whose ``limits`` map is ``limits``."""
    plan = SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        interval=SubscriptionInterval.MONTHLY,
        amount=99.0,
        currency="USD",
        is_active=True,
        limits=limits,
    )
    db.add(plan)
    await db.flush()
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=uuid.uuid4(),
        practice_id=practice_id,
        plan_id=plan.id,
        status=status,
        interval=SubscriptionInterval.MONTHLY,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    return plan


def _patient_payload(seed: str) -> dict:
    return {
        "first_name": "Quota",
        "last_name": "Patient",
        "email": f"quota.{seed}@example.com",
        "phone": f"+1999{seed[-8:]}".replace("-", ""),
        "date_of_birth": "1985-05-15",
        "gender": "female",
        "address_street": "1 Quota Ave",
        "address_city": "Springfield",
        "address_state": "IL",
        "address_zip": "62702",
        "emergency_contact": {
            "name": "Next of Kin",
            "relationship": "spouse",
            "phone": "+1987654322",
        },
        "medical_alerts": [],
        "status": "active",
    }


class TestPatientQuota:
    @pytest.mark.asyncio
    async def test_patient_creation_blocked_at_limit(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        """Once ``limits.patients`` is reached, further creates return 403."""
        await _add_active_plan(db_session, other_practice.id, {"patients": 1})

        first = await client.post(
            "/api/v1/patients",
            json=_patient_payload("aaa"),
            headers=other_auth_headers,
        )
        assert first.status_code == 201, first.text

        second = await client.post(
            "/api/v1/patients",
            json=_patient_payload("bbb"),
            headers=other_auth_headers,
        )
        assert second.status_code == 403, second.text
        assert "limit" in second.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_patient_creation_allowed_below_limit(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        """A host room exists below the ceiling; creation succeeds."""
        await _add_active_plan(db_session, other_practice.id, {"patients": 5})

        response = await client.post(
            "/api/v1/patients",
            json=_patient_payload("ccc"),
            headers=other_auth_headers,
        )
        assert response.status_code == 201, response.text

    @pytest.mark.asyncio
    async def test_no_subscription_bypasses_enforcement(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Practices without a subscription keep historical (unlimited) behavior."""
        response = await client.post(
            "/api/v1/patients",
            json=_patient_payload("ddd"),
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text

    @pytest.mark.asyncio
    async def test_plan_without_dimension_limit_bypasses_enforcement(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        """A plan that does not configure the dimension is unlimited for it."""
        await _add_active_plan(db_session, other_practice.id, {"storage_gb": 50})

        response = await client.post(
            "/api/v1/patients",
            json=_patient_payload("eee"),
            headers=other_auth_headers,
        )
        assert response.status_code == 201, response.text

    @pytest.mark.asyncio
    async def test_negative_limit_means_unlimited(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        await _add_active_plan(db_session, other_practice.id, {"patients": -1})

        response = await client.post(
            "/api/v1/patients",
            json=_patient_payload("fff"),
            headers=other_auth_headers,
        )
        assert response.status_code == 201, response.text


class TestStaffQuota:
    @pytest.mark.asyncio
    async def test_staff_creation_blocked_at_seat_limit(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        """The owner already occupies seat 1, so ``users: 1`` blocks new hires."""
        await _add_active_plan(db_session, other_practice.id, {"users": 1})

        response = await client.post(
            "/api/v1/staff/",
            headers=other_auth_headers,
            json={
                "email": f"newhire.{uuid.uuid4().hex[:8]}@example.com",
                "password": "StrongPass123!",
                "first_name": "New",
                "last_name": "Hire",
                "role": "FRONT_DESK",
                "practice_id": str(other_practice.id),
            },
        )
        assert response.status_code == 403, response.text
        assert "limit" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_staff_creation_allowed_with_seats_free(
        self,
        client: AsyncClient,
        other_auth_headers: dict,
        other_practice,
        db_session: AsyncSession,
    ):
        await _add_active_plan(db_session, other_practice.id, {"users": 5})

        response = await client.post(
            "/api/v1/staff/",
            headers=other_auth_headers,
            json={
                "email": f"newhire2.{uuid.uuid4().hex[:8]}@example.com",
                "password": "StrongPass123!",
                "first_name": "Second",
                "last_name": "Hire",
                "role": "FRONT_DESK",
                "practice_id": str(other_practice.id),
            },
        )
        assert response.status_code == 201, response.text


class TestInvitationQuota:
    @pytest.mark.asyncio
    async def test_invitation_accept_blocked_at_seat_limit(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_practice,
        db_session: AsyncSession,
    ):
        """The public invite-accept path cannot exceed plan limits.users."""
        from datetime import datetime, timedelta, timezone as _tz

        from app.core.security import generate_password_reset_token, hash_token
        from app.models.staff_invitation import StaffInvitation
        from app.models.user import UserRole

        # test_user already occupies seat 1 for test_practice.
        await _add_active_plan(db_session, test_practice.id, {"users": 1})

        email = f"invite.{uuid.uuid4().hex[:8]}@example.com"
        token = generate_password_reset_token()
        invitation = StaffInvitation(
            practice_id=test_practice.id,
            email=email,
            first_name="Invited",
            last_name="Seat",
            role=UserRole.DENTIST,
            token_hash=hash_token(token),
            expires_at=datetime.now(_tz.utc) + timedelta(hours=72),
        )
        db_session.add(invitation)
        await db_session.commit()

        accept = await client.post(
            "/api/v1/auth/invitations/accept",
            json={"token": token, "password": "ChosenPass123!"},
        )
        assert accept.status_code == 403, accept.text
        assert "limit" in accept.json()["detail"].lower()