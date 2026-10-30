"""
Token Revocation (Access-Token Blacklist)
=========================================

When a user logs out, their *refresh* token session is deleted from the DB,
preventing new access tokens from being minted.  However, the current access
token (short-lived, default 15 min) remains valid until it expires.

For defense-in-depth — particularly HIPAA session management — we maintain a
**revocation set**.  On logout, the access token's ``jti`` (JWT ID) is
recorded with a TTL equal to the remaining token lifetime.  On every
authenticated request, ``get_current_user`` checks the set and rejects revoked
tokens.

H-01 FIX — why there are two stores
-----------------------------------
This module used to keep revocations in Redis with an in-process ``deque``
fallback. Two problems:

1. The deque is per-worker. A revocation written by worker A was invisible to
   worker B.
2. On a Redis error, ``is_revoked`` returned ``jti in _fallback`` — so a
   revoked token kept authenticating on every worker whose local deque did not
   contain that jti. Revocation failed **open**.

Simply failing closed on Redis errors is not acceptable either: it would
reject every authenticated request during any Redis blip.

So revocation is now durable. ``revoke_token`` writes the ``revoked_tokens``
table (authoritative, shared, transactional) *and* Redis (a cache).
``is_revoked`` reads Redis first and falls through to the database when Redis
is unavailable. Correctness no longer depends on Redis; neither does
availability, because the database is already on the request path.

The in-process set is retained only as a same-process write-through cache for
the window between a write and its visibility; it is never the sole authority.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config_simple import settings

logger = logging.getLogger(__name__)

# Same-process write-through cache. Never the sole authority (see module docs).
_fallback: deque[str] = deque(maxlen=10_000)

_REDIS_PREFIX = "revoked:"
_redis_client: Any = None
_redis_client_url: Optional[str] = None


def _redis():
    """Return a cached Redis client for the configured URL or None."""
    global _redis_client, _redis_client_url
    url = getattr(settings, "REDIS_URL", None) or ""
    if not url:
        _redis_client = None
        _redis_client_url = None
        return None
    if _redis_client is not None and _redis_client_url == url:
        return _redis_client
    try:
        import redis as redis_lib

        _redis_client = redis_lib.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client_url = url
        return _redis_client
    except Exception:
        _redis_client = None
        _redis_client_url = None
        return None


async def revoke_token_durable(
    db,
    jti: str,
    ttl_seconds: int,
    *,
    user_id: Optional[UUID] = None,
    reason: Optional[str] = None,
) -> None:
    """Record a revocation durably, then cache it in Redis.

    The database write is the one that matters: it is visible to every worker
    and survives a Redis restart. It is flushed but **not committed** here, so
    it participates in the caller's transaction (logout also deletes the
    refresh session; the two must land together).

    Redis and the in-process set are best-effort caches. A cache failure is
    logged but never raised — the durable record already guarantees the token
    is rejected.
    """
    if not jti or ttl_seconds <= 0:
        return

    from app.models.revoked_token import RevokedToken

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    try:
        existing = (
            await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                RevokedToken(
                    jti=jti,
                    user_id=user_id,
                    expires_at=expires_at,
                    reason=reason,
                )
            )
            await db.flush()
    except IntegrityError:
        # Concurrent revocation of the same token: already recorded.
        logger.debug("Token %s was concurrently revoked", jti)
    except SQLAlchemyError as exc:
        # A durable-store failure IS worth surfacing: without it we cannot
        # promise the token is dead. The caller (logout) decides what to do,
        # but it must not be swallowed here.
        logger.critical("Durable token revocation failed for jti=%s: %s", jti, exc)
        raise

    _cache_revocation(jti, ttl_seconds)


def _cache_revocation(jti: str, ttl_seconds: int) -> None:
    """Best-effort cache write. Never raises."""
    _fallback.append(jti)
    r = _redis()
    if not r:
        return
    try:
        r.set(f"{_REDIS_PREFIX}{jti}", "1", ex=ttl_seconds)
    except Exception as exc:
        logger.warning(
            "Redis revocation cache write failed for jti=%s (durable record "
            "already stored, so revocation still applies): %s",
            jti,
            exc,
        )


def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Cache-only revocation.

    Retained for callers that have no database session available. This alone
    is **not** a durable revocation — prefer :func:`revoke_token_durable`.
    """
    if not jti or ttl_seconds <= 0:
        return
    logger.warning(
        "revoke_token() called without a database session; revocation for "
        "jti=%s is cache-only and will not survive a Redis restart. Use "
        "revoke_token_durable() where a session is available.",
        jti,
    )
    _cache_revocation(jti, ttl_seconds)


def is_revoked_cached(jti: str) -> Optional[bool]:
    """Consult only the caches.

    Returns ``True``/``False`` when a cache could answer authoritatively, and
    ``None`` when the caches are unavailable or inconclusive, meaning the
    caller must consult the durable store.
    """
    if not jti:
        return False
    if jti in _fallback:
        return True
    r = _redis()
    if r is None:
        # No Redis configured at all: the durable store is the only authority.
        return None
    try:
        return r.exists(f"{_REDIS_PREFIX}{jti}") == 1
    except Exception as exc:
        logger.error(
            "Redis revocation check failed for jti=%s; falling through to the "
            "durable store: %s",
            jti,
            exc,
        )
        return None


async def is_revoked(db, jti: str) -> bool:
    """Return True if the token identified by *jti* has been revoked.

    A positive hit in the local write-through deque or Redis short-circuits
    immediately. On a cache miss (`False` or `None`), we always verify against
    the durable ``revoked_tokens`` table so a missed Redis write, eviction, or
    Redis restart never allows a revoked token to authenticate.
    """
    if not jti:
        return False

    cached = is_revoked_cached(jti)
    if cached is True:
        return True

    from app.models.revoked_token import RevokedToken

    try:
        row = (
            await db.execute(
                select(RevokedToken.jti).where(
                    RevokedToken.jti == jti,
                    RevokedToken.expires_at > datetime.now(timezone.utc),
                )
            )
        ).scalar_one_or_none()
    except Exception as exc:
        logger.critical(
            "Database unavailable for the revocation check on jti=%s; "
            "failing closed: %s",
            jti,
            exc,
        )
        return True

    if row is not None:
        # Warm the local cache so subsequent requests avoid the database.
        _fallback.append(jti)
        return True
    return False


def is_revoked_sync(db, jti: str) -> bool:
    """Synchronous counterpart of :func:`is_revoked` for sync ``Session`` routes."""
    if not jti:
        return False

    cached = is_revoked_cached(jti)
    if cached is True:
        return True

    from app.models.revoked_token import RevokedToken

    try:
        row = db.execute(
            select(RevokedToken.jti).where(
                RevokedToken.jti == jti,
                RevokedToken.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one_or_none()
    except Exception as exc:
        logger.critical(
            "Database unavailable for sync revocation check on jti=%s; "
            "failing closed: %s",
            jti,
            exc,
        )
        return True

    if row is not None:
        _fallback.append(jti)
        return True
    return False


async def purge_expired_revocations(db) -> int:
    """Delete revocation rows whose tokens have already expired.

    After a token's own ``exp`` passes it is rejected by signature validation,
    so the revocation row carries no further information. Returns the number of
    rows removed.
    """
    from app.models.revoked_token import RevokedToken

    result = await db.execute(
        delete(RevokedToken).where(
            RevokedToken.expires_at < datetime.now(timezone.utc)
        )
    )
    return int(result.rowcount or 0)


def purge_expired_revocations_sync(db) -> int:
    """Sync version of purge_expired_revocations for Celery worker."""
    from app.models.revoked_token import RevokedToken

    result = (
        db.query(RevokedToken)
        .filter(RevokedToken.expires_at < datetime.now(timezone.utc))
        .delete(synchronize_session=False)
    )
    return int(result or 0)
