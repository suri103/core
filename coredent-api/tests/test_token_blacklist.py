"""Tests for durable access-token revocation and its caches."""
from __future__ import annotations

from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def fresh_blacklist(monkeypatch):
    """Reload the module with Redis disabled and a clean local cache."""
    monkeypatch.setenv("REDIS_URL", "")
    from app.core import config_simple
    import importlib

    importlib.reload(config_simple)
    from app.core import token_blacklist

    importlib.reload(token_blacklist)
    token_blacklist._fallback = deque(maxlen=10_000)
    token_blacklist._redis_client = None
    token_blacklist._redis_client_url = None
    return token_blacklist


def test_revoke_with_empty_jti_is_noop(fresh_blacklist):
    fresh_blacklist.revoke_token("", 60)
    fresh_blacklist.revoke_token("", 0)
    fresh_blacklist.revoke_token("", -5)
    assert len(fresh_blacklist._fallback) == 0


def test_revoke_with_zero_or_negative_ttl_is_noop(fresh_blacklist):
    fresh_blacklist.revoke_token("valid-jti-a", 0)
    fresh_blacklist.revoke_token("valid-jti-b", -1)
    assert len(fresh_blacklist._fallback) == 0
    # With Redis disabled, the cache cannot answer an unknown token; the
    # durable lookup is what the authenticated request path must use.
    assert fresh_blacklist.is_revoked_cached("valid-jti-a") is None
    assert fresh_blacklist.is_revoked_cached("valid-jti-b") is None


def test_cache_only_revoke_stores_in_fallback(fresh_blacklist):
    """The legacy cache-only API is visible locally but is not durable."""
    fresh_blacklist.revoke_token("jti-1", 60)
    assert "jti-1" in fresh_blacklist._fallback
    assert fresh_blacklist.is_revoked_cached("jti-1") is True


def test_durable_revoke_writes_database_and_cache(fresh_blacklist):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    db.flush = AsyncMock()

    import asyncio

    asyncio.run(
        fresh_blacklist.revoke_token_durable(
            db, "durable-jti", 60, reason="logout"
        )
    )
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    assert fresh_blacklist.is_revoked_cached("durable-jti") is True


def test_is_revoked_queries_durable_store_when_cache_unavailable(fresh_blacklist):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    import asyncio

    assert asyncio.run(fresh_blacklist.is_revoked(db, "unknown-jti")) is False
    db.execute.assert_awaited_once()


def test_is_revoked_queries_durable_store_on_redis_cache_miss(fresh_blacklist):
    """Regression for C-1: a Redis cache miss (False) must still consult RevokedToken."""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value="evicted-jti"))
    )

    import asyncio

    with patch.object(fresh_blacklist, "_redis", return_value=mock_redis):
        assert asyncio.run(fresh_blacklist.is_revoked(db, "evicted-jti")) is True
    db.execute.assert_awaited_once()
    assert "evicted-jti" in fresh_blacklist._fallback


def test_is_revoked_sync_queries_durable_store(fresh_blacklist):
    """Regression for C-1: sync Session endpoints consult RevokedToken instead of failing closed when Redis is unset."""
    db = MagicMock()
    db.execute = MagicMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    assert fresh_blacklist.is_revoked_sync(db, "sync-valid-jti") is False
    db.execute.assert_called_once()

    db_revoked = MagicMock()
    db_revoked.execute = MagicMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value="sync-revoked-jti"))
    )
    assert fresh_blacklist.is_revoked_sync(db_revoked, "sync-revoked-jti") is True
    assert "sync-revoked-jti" in fresh_blacklist._fallback



def test_is_revoked_returns_true_for_durable_row(fresh_blacklist):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value="jti"))
    )

    import asyncio

    assert asyncio.run(fresh_blacklist.is_revoked(db, "jti")) is True
    assert "jti" in fresh_blacklist._fallback



def test_is_revoked_fails_closed_when_durable_store_errors(fresh_blacklist):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("database is down"))

    import asyncio

    assert asyncio.run(fresh_blacklist.is_revoked(db, "unknown-jti")) is True


def test_is_revoked_cached_empty_jti_is_false(fresh_blacklist):
    assert fresh_blacklist.is_revoked_cached("") is False


def test_fallback_deque_is_bounded(fresh_blacklist):
    fresh_blacklist._fallback = deque(maxlen=3)
    for jti in ("jti-1", "jti-2", "jti-3", "jti-4"):
        fresh_blacklist.revoke_token(jti, 60)
    assert "jti-1" not in fresh_blacklist._fallback
    assert "jti-4" in fresh_blacklist._fallback
    assert len(fresh_blacklist._fallback) == 3


def test_redis_cache_write_and_read(fresh_blacklist):
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1
    with patch.object(fresh_blacklist, "_redis", return_value=mock_redis):
        fresh_blacklist.revoke_token("redis-jti", 120)
        assert fresh_blacklist.is_revoked_cached("redis-jti") is True
    mock_redis.set.assert_called_once_with("revoked:redis-jti", "1", ex=120)
    # Write-through local caching is intentional; Redis is still the shared
    # cache used by other workers and the database remains authoritative.
    assert "redis-jti" in fresh_blacklist._fallback


def test_redis_cache_returns_false_when_key_absent(fresh_blacklist):
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0
    with patch.object(fresh_blacklist, "_redis", return_value=mock_redis):
        assert fresh_blacklist.is_revoked_cached("not-revoked") is False


def test_cache_write_failure_keeps_local_write_through_entry(fresh_blacklist):
    mock_redis = MagicMock()
    mock_redis.set.side_effect = RuntimeError("redis is down")
    with patch.object(fresh_blacklist, "_redis", return_value=mock_redis):
        fresh_blacklist.revoke_token("redis-fail-jti", 30)
    assert "redis-fail-jti" in fresh_blacklist._fallback


def test_cache_read_failure_is_inconclusive_without_database(fresh_blacklist):
    mock_redis = MagicMock()
    mock_redis.exists.side_effect = RuntimeError("redis is down")
    with patch.object(fresh_blacklist, "_redis", return_value=mock_redis):
        assert fresh_blacklist.is_revoked_cached("unknown") is None


def test_redis_helper_returns_none_when_url_unset(fresh_blacklist):
    assert fresh_blacklist._redis() is None


def test_redis_helper_returns_none_on_import_error(fresh_blacklist, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("redis not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert fresh_blacklist._redis() is None
