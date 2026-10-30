"""
Tests for Subscription Gating and Access Enforcement.

Verifies the production access control matrix:
- ACTIVE: allowed
- TRIALING: allowed until trial_end
- CANCELED: allowed until current_period_end
- PAST_DUE: allowed within 7-day grace period
- EXPIRED / UNPAID / INCOMPLETE / None: blocked (402 Payment Required)
- PAUSED: allowed until paused_until
- Bypass paths: /api/v1/subscriptions, /api/v1/stripe, /api/v1/auth allowed regardless of subscription status
"""
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _subscription_is_current
from app.core.config_simple import settings
from app.models.practice import Practice
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus, SubscriptionInterval


@pytest.fixture
async def subscription_plan(db_session: AsyncSession) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        id=uuid.uuid4(),
        name="Pro Plan",
        interval=SubscriptionInterval.MONTHLY,
        amount=199.00,
        currency="USD",
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()
    await db_session.refresh(plan)
    return plan


class TestSubscriptionCurrentPolicy:
    """Pure-logic tests for _subscription_is_current."""

    def test_active_is_current(self):
        sub = Subscription(status=SubscriptionStatus.ACTIVE)
        assert _subscription_is_current(sub, datetime.now(timezone.utc)) is True

    def test_trialing_within_window(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.TRIALING,
            trial_end=now + timedelta(days=5),
        )
        assert _subscription_is_current(sub, now) is True

    def test_trialing_expired(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.TRIALING,
            trial_end=now - timedelta(days=1),
        )
        assert _subscription_is_current(sub, now) is False

    def test_canceled_within_paid_period(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.CANCELED,
            current_period_end=now + timedelta(days=10),
        )
        assert _subscription_is_current(sub, now) is True

    def test_canceled_past_period(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.CANCELED,
            current_period_end=now - timedelta(days=1),
        )
        assert _subscription_is_current(sub, now) is False

    def test_past_due_within_grace_period(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.PAST_DUE,
            updated_at=now - timedelta(days=3),
        )
        assert _subscription_is_current(sub, now) is True

    def test_past_due_beyond_grace_period(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.PAST_DUE,
            updated_at=now - timedelta(days=10),
        )
        assert _subscription_is_current(sub, now) is False

    def test_paused_within_window(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.PAUSED,
            paused_until=now + timedelta(days=5),
        )
        assert _subscription_is_current(sub, now) is True

    def test_paused_expired(self):
        now = datetime.now(timezone.utc)
        sub = Subscription(
            status=SubscriptionStatus.PAUSED,
            paused_until=now - timedelta(days=1),
        )
        assert _subscription_is_current(sub, now) is False

    def test_unpaid_or_incomplete_blocked(self):
        now = datetime.now(timezone.utc)
        for s in (SubscriptionStatus.UNPAID, SubscriptionStatus.INCOMPLETE, SubscriptionStatus.EXPIRED):
            sub = Subscription(status=s)
            assert _subscription_is_current(sub, now) is False


class TestSubscriptionGatingEndpoints:
    """Tests subscription enforcement through request dispatch."""

    @pytest.mark.asyncio
    async def test_production_environment_blocks_without_subscription(
        self, client: AsyncClient, auth_headers: dict, monkeypatch
    ):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr("app.core.rate_limit._check_and_incr", lambda *args, **kwargs: (True, 30, 0))

        response = await client.get("/api/v1/patients", headers=auth_headers)
        assert response.status_code == 402
        assert "subscription" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_production_environment_allows_with_active_subscription(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_practice: Practice,
        subscription_plan: SubscriptionPlan,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr("app.core.rate_limit._check_and_incr", lambda *args, **kwargs: (True, 30, 0))

        sub = Subscription(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            plan_id=subscription_plan.id,
            status=SubscriptionStatus.ACTIVE,
            interval=SubscriptionInterval.MONTHLY,
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(sub)
        await db_session.commit()

        response = await client.get("/api/v1/patients", headers=auth_headers)
        assert response.status_code == 200, response.json()

    @pytest.mark.asyncio
    async def test_subscription_management_routes_bypass_gating(
        self, client: AsyncClient, auth_headers: dict, monkeypatch
    ):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr("app.core.rate_limit._check_and_incr", lambda *args, **kwargs: (True, 30, 0))

        # In production without an active subscription, subscription endpoints
        # must remain reachable so practices can renew or view plans.
        response = await client.get("/api/v1/subscriptions/plans", headers=auth_headers)
        assert response.status_code == 200
