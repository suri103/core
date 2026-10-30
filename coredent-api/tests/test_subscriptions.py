"""
Async tests for Subscription API endpoints.
"""

import pytest
from unittest.mock import patch

from app.models.subscription import SubscriptionPlan, SubscriptionInterval

pytestmark = pytest.mark.asyncio


class TestSubscriptionPlans:
    """Test subscription plan endpoints"""

    async def test_create_subscription_plan(self, client, auth_headers):
        """Test creating a subscription plan"""
        plan_data = {
            "name": "Basic Plan",
            "description": "Essential features for small practices",
            "amount": 49.00,
            "currency": "USD",
            "interval": "monthly",
            "trial_period_days": 14,
            "features": ["Patient Management", "Appointment Scheduling"],
            "is_active": True,
        }
        response = await client.post(
            "/api/v1/subscriptions/plans",
            json=plan_data,
            headers=auth_headers,
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["name"] == "Basic Plan"
        assert data["interval"] == "monthly"

    async def test_list_subscription_plans(self, client, auth_headers):
        """Test listing subscription plans"""
        response = await client.get(
            "/api/v1/subscriptions/plans",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data

    async def test_get_plan_by_id(self, client, auth_headers, db_session, test_practice):
        """Test getting a specific subscription plan"""
        plan = SubscriptionPlan(
            practice_id=test_practice.id,
            name="Get Plan",
            amount=29.00,
            currency="USD",
            interval=SubscriptionInterval.MONTHLY,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/subscriptions/plans/{plan.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Plan"

    async def test_update_subscription_plan(self, client, auth_headers, db_session, test_practice):
        """Test updating a subscription plan"""
        plan = SubscriptionPlan(
            practice_id=test_practice.id,
            name="Update Plan",
            amount=29.00,
            currency="USD",
            interval=SubscriptionInterval.MONTHLY,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/subscriptions/plans/{plan.id}",
            json={"name": "Updated Plan"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Plan"

    async def test_deactivate_subscription_plan(self, client, auth_headers, db_session, test_practice):
        """Test deactivating a subscription plan via update"""
        plan = SubscriptionPlan(
            practice_id=test_practice.id,
            name="Deactivate Plan",
            amount=19.00,
            currency="USD",
            interval=SubscriptionInterval.MONTHLY,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/subscriptions/plans/{plan.id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False


class TestSubscriptionOwnership:
    async def test_cannot_read_other_practice_plan(self, client, auth_headers, db_session, other_practice):
        plan = SubscriptionPlan(
            practice_id=other_practice.id,
            name="Other Practice Plan",
            amount=29.00,
            currency="USD",
            interval=SubscriptionInterval.MONTHLY,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.get(f"/api/v1/subscriptions/plans/{plan.id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_cannot_update_other_practice_plan(self, client, auth_headers, db_session, other_practice):
        plan = SubscriptionPlan(
            practice_id=other_practice.id,
            name="Other Practice Plan",
            amount=29.00,
            currency="USD",
            interval=SubscriptionInterval.MONTHLY,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/subscriptions/plans/{plan.id}",
            headers=auth_headers,
            json={"name": "Tampered"},
        )
        assert response.status_code == 404


class TestSubscriptionStats:
    """Test subscription statistics endpoint"""

    async def test_get_stats(self, client, auth_headers):
        """Test getting subscription statistics"""
        response = await client.get(
            "/api/v1/subscriptions/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()
        assert "total_active" in data
        assert "mrr" in data
        assert "churn_rate" in data


class TestSubscriptionEmails:
    """Test subscription email notifications"""

    async def test_send_welcome_email(self):
        """Test sending subscription welcome email"""
        from app.core.email import email_service
        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = {"success": True, "message_id": "test-123"}
            result = await email_service.send_subscription_welcome(
                to="test@example.com",
                customer_name="John Doe",
                plan_name="Basic Plan",
                amount=49.00,
                interval="monthly",
                trial_end_date="2026-05-01",
            )
            assert result["success"] is True
            mock_send.assert_called_once()

    async def test_send_payment_receipt(self):
        """Test sending payment receipt email"""
        from app.core.email import email_service
        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = {"success": True, "message_id": "test-123"}
            result = await email_service.send_payment_receipt(
                to="test@example.com",
                customer_name="John Doe",
                amount=49.00,
                invoice_number="INV-001",
                payment_date="2026-04-07",
                plan_name="Basic Plan",
            )
            assert result["success"] is True
            mock_send.assert_called_once()

    async def test_send_payment_failed(self):
        """Test sending payment failed email"""
        from app.core.email import email_service
        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = {"success": True, "message_id": "test-123"}
            result = await email_service.send_payment_failed(
                to="test@example.com",
                customer_name="John Doe",
                amount=49.00,
                error_message="Card declined",
                retry_date="2026-04-10",
                attempt_number=1,
                max_attempts=4,
            )
            assert result["success"] is True
            mock_send.assert_called_once()

    async def test_send_trial_expiring(self):
        """Test sending trial expiring email"""
        from app.core.email import email_service
        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = {"success": True, "message_id": "test-123"}
            result = await email_service.send_trial_expiring(
                to="test@example.com",
                customer_name="John Doe",
                plan_name="Basic Plan",
                trial_end_date="2026-04-21",
                days_remaining=7,
                amount=49.00,
                interval="monthly",
            )
            assert result["success"] is True
            mock_send.assert_called_once()

    async def test_send_subscription_canceled(self):
        """Test sending subscription canceled email"""
        from app.core.email import email_service
        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = {"success": True, "message_id": "test-123"}
            result = await email_service.send_subscription_canceled(
                to="test@example.com",
                customer_name="John Doe",
                plan_name="Basic Plan",
                cancellation_date="2026-04-07",
                reason="Too expensive",
            )
            assert result["success"] is True
            mock_send.assert_called_once()