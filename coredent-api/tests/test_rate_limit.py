"""
Tests for app/core/rate_limit.py (per-user rate limiter).

The module layers a per-user cap on top of slowapi's per-IP cap. We
exercise:
- Rate-string parsing
- The Redis-backed INCR/EXPIRE path
- The fail-open path when Redis is unavailable
- The decorator wiring (HTTP 429 with Retry-After)
- IP fallback when no JWT is present
"""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.core.config_simple import settings
from app.core.rate_limit import (
    _parse_rate,
    _user_key,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rl_module(monkeypatch):
    """Reload rate_limit with a clean module-level state."""
    monkeypatch.setenv("REDIS_URL", "")
    from app.core import config_simple
    importlib.reload(config_simple)
    from app.core import rate_limit
    importlib.reload(rate_limit)
    # Ensure no cached Redis client leaks between tests
    rate_limit._redis_client = None
    return rate_limit


def _make_request(headers=None, client=("testclient", 50000), path="/"):
    """Build a minimal Starlette Request with the given headers and client."""
    from starlette.requests import Request
    headers = headers or {}
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "server": ("testserver", 80),
        "client": client,
        "scheme": "http",
        "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=receive)


def _make_jwt(sub: str = "user-123", practice_id: str | None = None) -> str:
    payload = {
        "sub": sub,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    if practice_id:
        payload["practice_id"] = practice_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# ---------------------------------------------------------------------------
# _parse_rate
# ---------------------------------------------------------------------------

class TestParseRate:
    @pytest.mark.parametrize("rate,expected", [
        ("30/minute", (30, 60)),
        ("5/second", (5, 1)),
        ("100/hour", (100, 3600)),
        ("1000/day", (1000, 86400)),
    ])
    def test_supported_units(self, rate, expected):
        assert _parse_rate(rate) == expected

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown rate unit"):
            _parse_rate("10/parsec")

    def test_strips_whitespace(self):
        assert _parse_rate("  30 / minute  ") == (30, 60)


# ---------------------------------------------------------------------------
# _user_key
# ---------------------------------------------------------------------------

class TestUserKey:
    def test_jwt_subject_takes_precedence(self):
        token = _make_jwt(sub="user-42")
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _user_key(request) == "user:user-42"

    def test_jwt_without_sub_falls_through_to_ip(self):
        # Manually encode a JWT without 'sub'
        payload = {
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        request = _make_request(
            headers={"Authorization": f"Bearer {token}"},
            client=("1.2.3.4", 50000),
        )
        # Falls back to IP
        assert _user_key(request).startswith("ip:")

    def test_invalid_jwt_falls_through_to_ip(self):
        request = _make_request(
            headers={"Authorization": "Bearer not-a-real-jwt"},
            client=("1.2.3.4", 50000),
        )
        assert _user_key(request) == "ip:1.2.3.4"

    def test_xff_used_only_through_configured_proxy(self, monkeypatch):
        from app.core import client_ip

        monkeypatch.setattr(client_ip.settings, "TRUSTED_PROXIES", "127.0.0.1")
        client_ip.reset_trusted_proxy_cache()
        request = _make_request(
            headers={"X-Forwarded-For": "10.0.0.5, 127.0.0.1"},
            client=("127.0.0.1", 50000),
        )
        # Walk from the nearest proxy hop: the configured proxy is skipped and
        # the first untrusted address is the actual client.
        assert _user_key(request) == "ip:10.0.0.5"

    def test_untrusted_peer_cannot_spoof_xff(self, monkeypatch):
        from app.core import client_ip

        monkeypatch.setattr(client_ip.settings, "TRUSTED_PROXIES", "127.0.0.1")
        client_ip.reset_trusted_proxy_cache()
        request = _make_request(
            headers={"X-Forwarded-For": "10.0.0.5"},
            client=("8.8.8.8", 50000),
        )
        assert _user_key(request) == "ip:8.8.8.8"

    def test_no_client_returns_unknown(self):
        from starlette.requests import Request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": None,
            "scheme": "http",
            "root_path": "",
        }
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        request = Request(scope, receive=receive)
        assert _user_key(request) == "ip:unknown"


# ---------------------------------------------------------------------------
# _get_redis
# ---------------------------------------------------------------------------

class TestGetRedis:
    def test_returns_none_when_no_url(self, rl_module):
        # fresh fixture set REDIS_URL="" so this is the default
        assert rl_module._redis_client is None
        assert rl_module._get_redis() is None

    def test_returns_cached_client_when_healthy(self, rl_module, monkeypatch):
        """When REDIS_URL is set and the cached client pings, return it."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from app.core import config_simple
        importlib.reload(config_simple)
        # Reload rate_limit so it picks up the new settings
        from app.core import rate_limit
        importlib.reload(rate_limit)
        fake_redis = MagicMock()
        fake_redis.ping.return_value = True
        rate_limit._redis_client = fake_redis
        assert rate_limit._get_redis() is fake_redis

    def test_resets_cached_client_when_ping_fails(self, rl_module, monkeypatch):
        """A stale cached client that fails ping must be dropped."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from app.core import config_simple
        importlib.reload(config_simple)
        from app.core import rate_limit
        importlib.reload(rate_limit)
        stale = MagicMock()
        stale.ping.side_effect = ConnectionError("stale")
        rate_limit._redis_client = stale
        # The stale client is dropped; with REDIS_URL set, _get_redis will
        # try to reconnect. Monkeypatch the redis import to also fail so
        # the result is None and the cached reference is cleared.
        with patch("redis.from_url", side_effect=ConnectionError("can't connect")):
            assert rate_limit._get_redis() is None
        assert rate_limit._redis_client is None


# ---------------------------------------------------------------------------
# _check_and_incr
# ---------------------------------------------------------------------------

class TestCheckAndIncr:
    def test_fails_open_when_redis_unavailable(self, rl_module):
        """No Redis -> always allow (fail open, documented behavior)."""
        allowed, remaining, retry = rl_module._check_and_incr("user:x", "5/minute")
        assert allowed is True
        assert remaining == 5
        assert retry == 0

    def test_allows_under_limit(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 1  # First call
        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            allowed, remaining, retry = rl_module._check_and_incr("user:x", "5/minute")
        assert allowed is True
        assert remaining == 4
        assert retry == 0
        # TTL was set on the first call
        fake_redis.expire.assert_called_once()

    def test_allows_when_at_limit(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 5
        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            allowed, remaining, retry = rl_module._check_and_incr("user:x", "5/minute")
        assert allowed is True
        assert remaining == 0
        assert retry == 0

    def test_blocks_over_limit(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 6
        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            allowed, remaining, retry = rl_module._check_and_incr("user:x", "5/minute")
        assert allowed is False
        assert remaining == 0
        assert retry >= 1  # retry_after > 0

    def test_does_not_set_ttl_on_subsequent_calls(self, rl_module):
        """Only the first INCR (returning 1) sets EXPIRE; subsequent calls
        must not touch TTL — Redis would silently extend the window."""
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 3
        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            rl_module._check_and_incr("user:x", "5/minute")
        fake_redis.expire.assert_not_called()

    def test_fails_open_on_redis_error(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.side_effect = ConnectionError("redis died")
        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            allowed, remaining, retry = rl_module._check_and_incr("user:x", "5/minute")
        assert allowed is True
        assert remaining == 5
        assert retry == 0
    def test_fails_closed_when_redis_unavailable_in_production(self, rl_module):
        with patch.object(rl_module.settings, "ENVIRONMENT", "production"):
            with patch.object(rl_module, "_get_redis", return_value=None):
                with pytest.raises(rl_module.RateLimitBackendUnavailable):
                    rl_module._check_and_incr("user:x", "5/minute")

    def test_fails_closed_on_redis_error_in_production(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.side_effect = ConnectionError("redis died")
        with patch.object(rl_module.settings, "ENVIRONMENT", "production"):
            with patch.object(rl_module, "_get_redis", return_value=fake_redis):
                with pytest.raises(rl_module.RateLimitBackendUnavailable):
                    rl_module._check_and_incr("user:x", "5/minute")


# ---------------------------------------------------------------------------
# user_rate_limit decorator
# ---------------------------------------------------------------------------

class TestUserRateLimitDecorator:
    @pytest.mark.asyncio
    async def test_passes_through_when_allowed(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 1
        request = _make_request()

        @rl_module.user_rate_limit("5/minute")
        async def handler(request):
            return "ok"

        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            result = await handler(request=request)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_raises_429_when_over_limit(self, rl_module):
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 100
        request = _make_request()

        @rl_module.user_rate_limit("5/minute")
        async def handler(request):
            return "should not reach"

        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            with pytest.raises(rl_module.HTTPException) as excinfo:
                await handler(request=request)
        assert excinfo.value.status_code == 429
        assert "Retry-After" in excinfo.value.headers
        assert int(excinfo.value.headers["Retry-After"]) >= 1

    @pytest.mark.asyncio
    async def test_passes_through_when_no_request_in_args(self, rl_module):
        """L-15 FIX: a missing Request must fail closed (programmer error),
        not silently disable the per-user PHI cap."""

        @rl_module.user_rate_limit("5/minute")
        async def handler(some_other_arg):
            return "ok"

        with pytest.raises(RuntimeError, match="request: Request"):
            await handler(some_other_arg=42)

    @pytest.mark.asyncio
    async def test_request_in_positional_args(self, rl_module):
        """Some FastAPI routes pass Request positionally."""
        fake_redis = MagicMock()
        fake_redis.incr.return_value = 1
        request = _make_request()

        @rl_module.user_rate_limit("5/minute")
        async def handler(request, other=None):
            return other

        with patch.object(rl_module, "_get_redis", return_value=fake_redis):
            result = await handler(request, other="x")
        assert result == "x"

    @pytest.mark.asyncio
    async def test_fails_open_when_redis_down(self, rl_module):
        request = _make_request()

        @rl_module.user_rate_limit("5/minute")
        async def handler(request):
            return "ok"

        with patch.object(rl_module, "_get_redis", return_value=None):
            result = await handler(request=request)
        assert result == "ok"
    @pytest.mark.asyncio
    async def test_returns_503_when_redis_down_in_production(self, rl_module):
        request = _make_request()

        @rl_module.user_rate_limit("5/minute")
        async def handler(request):
            return "should not reach"

        with patch.object(rl_module.settings, "ENVIRONMENT", "production"):
            with patch.object(rl_module, "_get_redis", return_value=None):
                with pytest.raises(rl_module.HTTPException) as excinfo:
                    await handler(request=request)

        assert excinfo.value.status_code == 503
        assert excinfo.value.headers == {"Retry-After": "5"}
