"""Shared slowapi limiter construction with production-safe Redis storage."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

import redis
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.client_ip import rate_limit_key

logger = logging.getLogger(__name__)


class RedisRateLimitUnavailable(RuntimeError):
    """Raised when a required Redis rate-limit backend cannot initialize."""


def create_limiter(
    redis_url: Optional[str] = None,
    *,
    default_limits: Optional[Sequence[str]] = None,
    require_redis: bool = False,
) -> Limiter:
    """Build the single limiter instance used by decorators and middleware.

    Production passes ``require_redis=True`` and refuses to start without a
    reachable backend. Outside production, an unavailable optional Redis URL
    falls back to process-local memory for developer convenience.
    """
    limits = list(default_limits or [])

    if not redis_url:
        if require_redis:
            raise RedisRateLimitUnavailable(
                "Redis is required for production rate limiting"
            )
        logger.info("Redis not configured; using in-memory rate-limit storage")
        return Limiter(key_func=rate_limit_key, default_limits=limits)

    try:
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        client.close()
    except Exception as exc:
        if require_redis:
            raise RedisRateLimitUnavailable(
                "Redis rate-limit backend is unavailable"
            ) from exc
        logger.warning(
            "Redis rate-limit backend unavailable; using in-memory storage outside production: %s",
            exc,
        )
        return Limiter(key_func=rate_limit_key, default_limits=limits)

    # slowapi/limits uses the synchronous redis-py backend here. The
    # async+redis URI selects coredis, which is a separate optional dependency
    # and is not required by this service. The limiter itself is synchronous
    # and is safe to invoke from FastAPI request handlers.
    logger.info("Redis-backed rate limiting initialized")
    return Limiter(
        key_func=rate_limit_key,
        default_limits=limits,
        storage_uri=redis_url,
        in_memory_fallback_enabled=False,
        swallow_errors=False,
    )


def setup_redis_rate_limit(
    app,
    redis_url: Optional[str] = None,
    *,
    require_redis: bool = False,
    default_limits: Optional[Sequence[str]] = None,
) -> bool:
    """Attach a limiter to a small standalone app before routes are declared.

    The production CoreDent application constructs its shared limiter in
    ``app.core.limiter`` so route decorators and middleware use one instance.
    This helper remains useful for isolated apps and tests.
    """
    limiter = create_limiter(
        redis_url,
        default_limits=default_limits,
        require_redis=require_redis,
    )
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "type": "rate_limit_exceeded"},
        ),
    )
    return bool(redis_url and limiter._storage_uri == redis_url)