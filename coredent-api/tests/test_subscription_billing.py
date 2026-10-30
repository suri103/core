"""Unit tests for subscription billing service mocked async methods."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.services.subscription_billing import SubscriptionBillingService
from app.models.subscription import SubscriptionStatus


@pytest.mark.asyncio
class TestCalculateMrr:
    async def test_empty_subscriptions(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await SubscriptionBillingService.calculate_mrr(mock_db, uuid4())
        assert result == Decimal("0")

    async def test_with_active_subscriptions(self):
        mock_db = AsyncMock()
        from app.models.subscription import SubscriptionInterval
        mock_sub1 = MagicMock()
        mock_sub1.plan.interval = SubscriptionInterval.MONTHLY
        mock_sub1.plan.amount = Decimal("100.00")
        mock_sub2 = MagicMock()
        mock_sub2.plan.interval = SubscriptionInterval.MONTHLY
        mock_sub2.plan.amount = Decimal("50.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_sub1, mock_sub2]
        mock_db.execute.return_value = mock_result

        result = await SubscriptionBillingService.calculate_mrr(mock_db, uuid4())
        assert result == Decimal("150.00")


@pytest.mark.asyncio
class TestCalculateChurnRate:
    async def test_no_subscriptions(self):
        mock_db = AsyncMock()
        mock_active = MagicMock()
        mock_active.scalar.return_value = 0
        mock_canceled = MagicMock()
        mock_canceled.scalar.return_value = 0
        mock_db.execute.side_effect = [mock_active, mock_canceled]

        result = await SubscriptionBillingService.calculate_churn_rate(mock_db, uuid4())
        assert result == 0.0

    async def test_with_churn(self):
        mock_db = AsyncMock()
        mock_active = MagicMock()
        mock_active.scalar.return_value = 90
        mock_canceled = MagicMock()
        mock_canceled.scalar.return_value = 10
        mock_db.execute.side_effect = [mock_active, mock_canceled]

        result = await SubscriptionBillingService.calculate_churn_rate(mock_db, uuid4())
        assert result == 10.0


@pytest.mark.asyncio
class TestCalculateAverageLifetime:
    async def test_no_subscriptions(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await SubscriptionBillingService.calculate_average_lifetime(mock_db, uuid4())
        assert result == 0.0

    async def test_with_subscriptions(self):
        mock_db = AsyncMock()
        now = datetime.now(timezone.utc)
        created_dates = [now - timedelta(days=30), now - timedelta(days=60)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = created_dates
        mock_db.execute.return_value = mock_result

        result = await SubscriptionBillingService.calculate_average_lifetime(mock_db, uuid4())
        assert result == pytest.approx(45.0, abs=0.1)

    async def test_with_naive_datetimes(self):
        mock_db = AsyncMock()
        now = datetime.now(timezone.utc)
        created_dates = [
            (now - timedelta(days=20)).replace(tzinfo=None),
            (now - timedelta(days=40)).replace(tzinfo=None),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = created_dates
        mock_db.execute.return_value = mock_result

        result = await SubscriptionBillingService.calculate_average_lifetime(mock_db, uuid4())
        assert result == pytest.approx(30.0, abs=0.1)


@pytest.mark.asyncio
class TestGetSubscriptionStats:
    async def test_returns_all_fields(self):
        mock_db = AsyncMock()

        # Status counts - return 0 for each
        status_results = []
        for _ in SubscriptionStatus:
            r = MagicMock()
            r.scalar.return_value = 0
            status_results.append(r)

        # MRR result
        mrr_result = MagicMock()
        mrr_result.scalars.return_value.all.return_value = []

        # Churn rate results
        churn_active = MagicMock()
        churn_active.scalar.return_value = 0
        churn_canceled = MagicMock()
        churn_canceled.scalar.return_value = 0

        # Average lifetime
        lifetime_result = MagicMock()
        lifetime_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = status_results + [mrr_result, churn_active, churn_canceled, lifetime_result]

        result = await SubscriptionBillingService.get_subscription_stats(mock_db, uuid4())
        assert "total_active" in result
        assert "total_trials" in result
        assert "mrr" in result
        assert "churn_rate" in result
        assert "mrr_growth_percent" in result
        assert "trial_conversion_rate" in result


@pytest.mark.asyncio
class TestProcessDunningEligibility:
    """The sweep must see every due past-due subscription.

    The stripe.py status-sync path flips subscriptions PAST_DUE without
    scheduling a retry instant, and ``NULL <= now`` never matches in SQL,
    so those rows used to be invisible to dunning.
    """

    async def _create_past_due_subscription(self, db_session, practice, next_retry_at):
        from app.models.subscription import Subscription, SubscriptionInterval, SubscriptionPlan

        plan = SubscriptionPlan(
            practice_id=practice.id,
            name="Dunning Test Plan",
            amount=Decimal("99.00"),
            interval=SubscriptionInterval.MONTHLY,
        )
        db_session.add(plan)
        await db_session.flush()

        subscription = Subscription(
            practice_id=practice.id,
            plan_id=plan.id,
            status=SubscriptionStatus.PAST_DUE,
            interval=SubscriptionInterval.MONTHLY,
            dunning_retry_count=0,
            dunning_max_retries=4,
            next_retry_at=next_retry_at,
        )
        db_session.add(subscription)
        await db_session.flush()
        return subscription

    async def test_null_next_retry_at_is_due(self, db_session, test_practice):
        sub = await self._create_past_due_subscription(db_session, test_practice, None)
        now_before = datetime.now(timezone.utc)

        result = await SubscriptionBillingService.process_dunning(
            db_session, MagicMock()
        )

        assert result["total"] == 1
        assert result["processed"] == 0
        assert result["failed"] == 1
        assert sub.dunning_retry_count == 1
        assert sub.next_retry_at is not None
        assert sub.next_retry_at > now_before

    async def test_future_next_retry_at_is_not_due(self, db_session, test_practice):
        await self._create_past_due_subscription(
            db_session,
            test_practice,
            datetime.now(timezone.utc) + timedelta(days=3),
        )

        result = await SubscriptionBillingService.process_dunning(
            db_session, MagicMock()
        )

        assert result["total"] == 0
