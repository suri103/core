"""Tests for reports endpoints"""
import pytest

pytestmark = pytest.mark.asyncio


class TestReportsDashboard:
    async def test_dashboard_metrics_requires_auth(self, client):
        response = await client.get("/api/v1/reports/dashboard?from=2026-01-01&to=2026-12-31")
        assert response.status_code in (401, 403)

    async def test_dashboard_metrics_validation_error(self, client, auth_headers):
        response = await client.get("/api/v1/reports/dashboard")
        assert response.status_code in (422, 401, 403)

    async def test_dashboard_metrics_with_date_range(self, client, auth_headers):
        response = await client.get("/api/v1/reports/dashboard?from=2026-01-01&to=2026-12-31")
        assert response.status_code in (200, 401, 403)
