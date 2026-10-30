"""Unit tests for subscription service pure functions and mocked async methods."""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.subscription_service import SubscriptionService
from app.models.subscription import SubscriptionInterval
from app.core.config_simple import settings


class TestCalculatePeriodStartEnd:
    def test_weekly(self):
        start, end = SubscriptionService.calculate_period_start_end(
            SubscriptionInterval.WEEKLY,
            datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        assert start.weekday() == 0
        assert (end - start).days == 7

    def test_monthly(self):
        start, end = SubscriptionService.calculate_period_start_end(
            SubscriptionInterval.MONTHLY,
            datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        assert start.day == 1
        assert end > start
        assert end.month == 6

    def test_quarterly(self):
        start, end = SubscriptionService.calculate_period_start_end(
            SubscriptionInterval.QUARTERLY,
            datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        assert start.month in (1, 4, 7, 10)
        assert end > start

    def test_annual(self):
        start, end = SubscriptionService.calculate_period_start_end(
            SubscriptionInterval.ANNUAL,
            datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        assert start.month == 1 and start.day == 1
        assert end.year == 2024

    def test_semi_annual(self):
        start, end = SubscriptionService.calculate_period_start_end(
            SubscriptionInterval.SEMI_ANNUAL,
            datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        assert start.month == 1
        assert end.year == 2024


class TestCalculateProrationAmount:
    def test_basic_proration(self):
        result = SubscriptionService.calculate_proration_amount(
            Decimal("100.00"), Decimal("150.00"), 15, 30
        )
        assert result == Decimal("25.00")

    def test_zero_days_total(self):
        result = SubscriptionService.calculate_proration_amount(
            Decimal("100.00"), Decimal("150.00"), 15, 0
        )
        assert result == Decimal("0")

    def test_negative_proration(self):
        result = SubscriptionService.calculate_proration_amount(
            Decimal("200.00"), Decimal("100.00"), 15, 30
        )
        assert result == Decimal("-50.00")


@pytest.mark.asyncio
class TestGetSubscriptionWithPlan:
    async def test_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"id": "sub-1"}
        mock_db.execute.return_value = mock_result

        result = await SubscriptionService.get_subscription_with_plan(
            mock_db, "550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440000"
        )
        assert result == {"id": "sub-1"}
        mock_db.execute.assert_called_once()

    async def test_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await SubscriptionService.get_subscription_with_plan(
            mock_db, "550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440000"
        )
        assert result is None


@pytest.mark.asyncio
class TestGetUsageRecords:
    async def test_returns_records(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["record1", "record2"]
        mock_db.execute.return_value = mock_result

        result = await SubscriptionService.get_usage_records(
            mock_db, "550e8400-e29b-41d4-a716-446655440000"
        )
        assert result == ["record1", "record2"]


# =====================================================================
# Subscription edge-case regression tests
# =====================================================================


class TestRecordUsageEdgeCases:
    @pytest.mark.asyncio
    async def test_rejects_non_positive_quantity(self):
        mock_db = AsyncMock()
        mock_sub = MagicMock()
        mock_sub.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_sub.plan_id = "550e8400-e29b-41d4-a716-446655440001"

        for bad in (Decimal("0"), Decimal("-1")):
            with pytest.raises(ValueError):
                await SubscriptionService.record_usage(mock_db, mock_sub, bad)

    @pytest.mark.asyncio
    async def test_rejects_none_quantity(self):
        mock_db = AsyncMock()
        mock_sub = MagicMock()

        with pytest.raises(ValueError):
            await SubscriptionService.record_usage(mock_db, mock_sub, None)

    @pytest.mark.asyncio
    async def test_rejects_excessive_quantity(self):
        mock_db = AsyncMock()
        mock_sub = MagicMock()
        mock_sub.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_sub.plan_id = "550e8400-e29b-41d4-a716-446655440001"
        mock_sub.current_usage = Decimal("0")
        mock_sub.current_overage = None

        from app.services.subscription_service import MAX_USAGE_QUANTITY

        with pytest.raises(ValueError):
            await SubscriptionService.record_usage(
                mock_db, mock_sub, MAX_USAGE_QUANTITY + Decimal("1")
            )


class TestChangePlanEdgeCases:
    @pytest.mark.asyncio
    async def test_same_plan_change_returns_zero_without_stripe(self, monkeypatch):
        mock_db = AsyncMock()
        mock_sub = MagicMock()
        mock_sub.plan_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_sub.id = "550e8400-e29b-41d4-a716-446655440002"

        new_plan = MagicMock()
        new_plan.id = "550e8400-e29b-41d4-a716-446655440000"

        import stripe as stripe_lib

        monkeypatch.setattr(settings, "STRIPE_API_KEY", "sk_test_dummy")
        retrieve = MagicMock()
        monkeypatch.setattr(stripe_lib.Subscription, "retrieve", retrieve)

        result = await SubscriptionService.change_plan(mock_db, mock_sub, new_plan)

        assert result == Decimal("0")
        # No Stripe round-trip for an identical plan.
        retrieve.assert_not_called()
        # Local subscription is not mutated.
        assert mock_sub.plan_id == "550e8400-e29b-41d4-a716-446655440000"
