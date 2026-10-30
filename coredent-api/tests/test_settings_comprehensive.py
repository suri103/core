"""
Comprehensive settings endpoint tests.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestBillingPreferences:
    """Billing preferences endpoint tests."""

    async def test_get_billing_preferences(self, client: AsyncClient, auth_headers):
        response = await client.get("/api/v1/settings/billing", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "taxRate" in data
        assert "currency" in data
        assert "invoicePrefix" in data
        assert "paymentTerms" in data

    async def test_update_billing_preferences(self, client: AsyncClient, auth_headers):
        response = await client.put(
            "/api/v1/settings/billing",
            headers=auth_headers,
            json={
                "taxRate": 8.5,
                "currency": "USD",
                "invoicePrefix": "INV-2026",
                "paymentTerms": 15,
                "lateFeePercentage": 5.0,
                "acceptedPaymentMethods": ["cash", "card"],
                "autoSendInvoices": True,
                "autoSendReminders": True,
                "reminderDaysBefore": 7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["taxRate"] == 8.5
        assert data["currency"] == "USD"
        assert data["invoicePrefix"] == "INV-2026"
        assert data["paymentTerms"] == 15
        assert data["autoSendInvoices"] is True
        assert data["reminderDaysBefore"] == 7

    async def test_update_billing_preferences_partial(self, client: AsyncClient, auth_headers):
        response = await client.put(
            "/api/v1/settings/billing",
            headers=auth_headers,
            json={"taxRate": 10.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["taxRate"] == 10.0
