"""Phase 3 regression tests: security headers + /metrics protection.

The security-headers middleware and the protected /metrics endpoint had no
test coverage — a refactor could silently drop CSP/XFO or expose metrics.
Headers are now applied in all environments for consistency.
"""
import pytest

pytestmark = pytest.mark.asyncio


class TestSecurityHeaders:
    async def test_health_response_carries_security_headers(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers["strict-transport-security"] == (
            "max-age=31536000; includeSubDomains; preload"
        )
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers["permissions-policy"]

    async def test_csp_header_present_and_hardened(self, client):
        response = await client.get("/health")
        csp = response.headers.get("content-security-policy", "")
        assert csp, "Content-Security-Policy header missing"
        assert "default-src 'self'" in csp
        assert "unsafe-inline" not in csp

    async def test_api_error_responses_also_carry_headers(self, client):
        # Headers must be applied by middleware on every response, not just
        # on success paths.
        response = await client.get("/api/v1/does-not-exist")
        assert response.headers.get("x-frame-options") == "DENY"


class TestMetricsProtection:
    @staticmethod
    def _production_metrics(monkeypatch):
        # Patch both import sites; they share the singleton but patching by
        # object identity is more reliable than by string path across reloads.
        from app.core.config_simple import settings as cfg_settings
        import app.main as main_mod

        monkeypatch.setattr(cfg_settings, "DEBUG", False)
        # main_mod.settings is the same object, but patch it explicitly for
        # robustness against future import divergence.
        if getattr(main_mod, "settings", None) is not cfg_settings:
            monkeypatch.setattr(main_mod.settings, "DEBUG", False)
        monkeypatch.setattr(cfg_settings, "MONITORING_TOKEN", "tok-123")
        if getattr(main_mod, "settings", None) is not cfg_settings:
            monkeypatch.setattr(main_mod.settings, "MONITORING_TOKEN", "tok-123")

    async def test_metrics_requires_token_when_debug_disabled(self, client, monkeypatch):
        self._production_metrics(monkeypatch)
        response = await client.get("/metrics")
        assert response.status_code in (401, 403)

    async def test_metrics_rejects_wrong_token(self, client, monkeypatch):
        self._production_metrics(monkeypatch)
        response = await client.get("/metrics", headers={"X-Monitoring-Token": "wrong"})
        assert response.status_code in (401, 403)

    async def test_metrics_allows_correct_token(self, client, monkeypatch):
        self._production_metrics(monkeypatch)
        response = await client.get("/metrics", headers={"X-Monitoring-Token": "tok-123"})
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
