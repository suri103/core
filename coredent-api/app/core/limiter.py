"""The single slowapi limiter shared by route decorators and the application."""

from app.core.config_simple import settings
from app.core.redis_rate_limit import create_limiter

limiter = create_limiter(
    settings.REDIS_URL or None,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    require_redis=settings.ENVIRONMENT == "production",
)