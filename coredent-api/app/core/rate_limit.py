"""
Per-User Rate Limiting
======================

The default slowapi limiter keys on the client IP.  Behind a reverse
proxy (Railway, Vercel, etc.) that means every user from the same
corporate NAT shares one bucket.  Worse, a single user from one IP
can blast 100 req/min at PHI endpoints with no per-user cap.

This module provides a Redis-backed per-user rate limiter that keys
on the JWT subject (``user_id``) for authenticated requests, and
falls back to IP for anonymous.  It is layered on top of slowapi, not
a replacement: slowapi still gives you the per-IP default cap; this
adds a tighter per-user cap for PHI endpoints.

Usage::

    from app.core.rate_limit import user_rate_limit

    @router.get("/patients")
    @user_rate_limit("30/minute")  # 30 list-requests per minute per user
    async def list_patients(...): ...

In production, Redis loss fails CLOSED with HTTP 503 so protected PHI
routes cannot silently lose their per-user control. Development and test
environments retain a logged fail-open fallback for local usability.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import redis

from fastapi import Request, HTTPException, status

from app.core.config_simple import settings

logger = logging.getLogger(__name__)


class RateLimitBackendUnavailable(RuntimeError):
    """Raised when production rate-limit state cannot be accessed safely."""


def _fail_open_allowed() -> bool:
    """Only non-production environments may continue without Redis."""
    return settings.ENVIRONMENT != "production"


# ---------------------------------------------------------------------------
# Redis client (lazy singleton)
# ---------------------------------------------------------------------------

_redis_client: Optional["redis.Redis"] = None


def _get_redis():
    """Return a Redis client, or None if Redis is not configured/unhealthy."""
    global _redis_client
    if not settings.REDIS_URL:
        return None
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
    try:
        import redis as redis_lib
        client = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        return client
    except Exception as exc:
        logger.warning("Per-user rate limit Redis connection failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _user_key(request: Request) -> str:
    """
    Return the rate-limit bucket key for this request.

    Order of preference:
      1. JWT subject (best — one bucket per logged-in user).
      2. Trusted client IP for anonymous endpoints.

    M-23 FIX: the IP is resolved by ``app.core.client_ip.get_client_ip``, which
    only honours ``X-Forwarded-For`` when the direct peer is a configured
    trusted proxy. This function previously took the leftmost value of that
    header unconditionally — a client-settable value — so a caller could rotate
    the header and get a fresh bucket on every request, evading the limiter.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        from app.core.security import decode_token
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            if payload and payload.get("sub"):
                return f"user:{payload['sub']}"
        except Exception:
            pass

    from app.core.client_ip import get_client_ip

    return f"ip:{get_client_ip(request)}"


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------


def _parse_rate(rate: str) -> tuple[int, int]:
    """
    Parse a rate string like ``"30/minute"`` into ``(count, window_seconds)``.

    Supports: ``/second``, ``/minute``, ``/hour``, ``/day``.
    """
    n, _, unit = rate.partition("/")
    count = int(n.strip())
    unit = unit.strip().lower()
    if unit.startswith("sec"):
        window = 1
    elif unit.startswith("min"):
        window = 60
    elif unit.startswith("hour"):
        window = 3600
    elif unit.startswith("day"):
        window = 86400
    else:
        raise ValueError(f"Unknown rate unit: {unit!r}")
    return count, window


def _check_and_incr(key_suffix: str, rate: str) -> tuple[bool, int, int]:
    """
    Atomically check + increment a rate-limit bucket.

    Returns ``(allowed, remaining, retry_after_seconds)``.
    """
    count, window = _parse_rate(rate)
    client = _get_redis()
    bucket = f"rl:{key_suffix}"
    now = int(time.time())
    window_start = now - (now % window)
    redis_key = f"{bucket}:{window_start}"

    if client is None:
        if _fail_open_allowed():
            logger.warning(
                "Per-user rate limit unavailable; allowing request outside production"
            )
            return True, count, 0
        raise RateLimitBackendUnavailable("Redis rate-limit backend unavailable")

    try:
        # INCR is atomic; first call returns 1, then 2, ...
        current = client.incr(redis_key)
        if current == 1:
            # Set TTL = current window.  EXPIRE is idempotent.
            client.expire(redis_key, window)
        if current > count:
            # Over limit.  Compute retry_after = time until window end.
            retry_after = max(1, window - (now - window_start))
            return False, 0, retry_after
        return True, max(0, count - current), 0
    except Exception as exc:
        if _fail_open_allowed():
            logger.warning(
                "Per-user rate limit Redis error; allowing request outside production: %s",
                exc,
            )
            return True, count, 0
        logger.error("Per-user rate limit Redis error in production: %s", exc)
        raise RateLimitBackendUnavailable(
            "Redis rate-limit backend unavailable"
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def user_rate_limit(rate: str):
    """
    Decorator factory: apply a per-user rate limit to a route.

    The limit is keyed on the JWT subject for authenticated requests
    and on the client IP for anonymous.  The IP-based slowapi limit
    is still active; this is layered on top.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the Request object in the args/kwargs so we can
            # inspect headers.  FastAPI typically passes it positionally
            # because the function is declared with ``request: Request``.
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for a in args:
                    if isinstance(a, Request):
                        request = a
                        break
            if request is None:
                # L-15 FIX: fail closed on programmer error — a forgotten
                # `request: Request` param must not silently disable the
                # per-user PHI cap. Log loudly so it surfaces in dev/CI.
                import logging as _logging

                _logging.getLogger(__name__).error(
                    "user_rate_limit: no Request found on %s — refusing to "
                    "run without a rate-limit key (add `request: Request`).",
                    getattr(func, "__name__", func),
                )
                raise RuntimeError(
                    "user_rate_limit requires `request: Request` on the route"
                )

            endpoint_name = getattr(func, "__qualname__", getattr(func, "__name__", "endpoint"))
            key = f"{endpoint_name}:{_user_key(request)}"
            try:
                allowed, remaining, retry_after = _check_and_incr(key, rate)
            except RateLimitBackendUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting service unavailable. Please retry shortly.",
                    headers={"Retry-After": "5"},
                ) from exc
            if not allowed:
                # Emit a Sentry breadcrumb so on-call can see who is
                # being throttled.
                try:
                    import sentry_sdk
                    with sentry_sdk.push_scope() as scope:
                        scope.set_tag("event_type", "rate_limit_user")
                        scope.set_context("rate_limit", {"key": key, "rate": rate})
                        sentry_sdk.add_breadcrumb(
                            category="rate_limit",
                            message=f"Per-user rate limit exceeded for {key}",
                            level="warning",
                        )
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Per-user rate limit exceeded: {rate}. Try again in {retry_after}s.",
                    headers={"Retry-After": str(retry_after)},
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
