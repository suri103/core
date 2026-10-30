"""Tests for production-safe slowapi Redis limiter construction."""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def rl_module(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    from app.core import config_simple
    importlib.reload(config_simple)
    from app.core import redis_rate_limit
    importlib.reload(redis_rate_limit)
    return redis_rate_limit


def test_create_uses_memory_when_no_url_outside_production(rl_module):
    limiter = rl_module.create_limiter(default_limits=["100/minute"])
    assert limiter._storage_uri is None


def test_create_falls_back_to_memory_on_optional_redis_failure(rl_module):
    fake_redis = MagicMock()
    fake_redis.ping.side_effect = ConnectionError("redis is down")
    with patch.object(rl_module.redis, "from_url", return_value=fake_redis):
        limiter = rl_module.create_limiter("redis://localhost:6379")
    assert limiter._storage_uri is None


def test_create_fails_startup_when_required_redis_is_down(rl_module):
    fake_redis = MagicMock()
    fake_redis.ping.side_effect = ConnectionError("redis is down")
    with patch.object(rl_module.redis, "from_url", return_value=fake_redis):
        with pytest.raises(rl_module.RedisRateLimitUnavailable):
            rl_module.create_limiter(
                "redis://localhost:6379",
                require_redis=True,
            )


def test_create_wires_redis_storage_on_success(rl_module):
    fake_redis = MagicMock()
    fake_redis.ping.return_value = True
    with patch.object(rl_module.redis, "from_url", return_value=fake_redis):
        limiter = rl_module.create_limiter("redis://localhost:6379")
    assert limiter._storage_uri == "redis://localhost:6379"
    assert limiter._in_memory_fallback_enabled is False


def test_setup_attaches_limiter_and_handler(rl_module):
    fake_app = MagicMock()
    result = rl_module.setup_redis_rate_limit(fake_app, redis_url=None)
    assert result is False
    assert fake_app.state.limiter._storage_uri is None
    fake_app.add_exception_handler.assert_called_once()


def test_dead_middleware_class_not_present(rl_module):
    assert not hasattr(rl_module, "RedisRateLimitMiddleware")