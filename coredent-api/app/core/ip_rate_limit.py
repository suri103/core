"""
IP-Based Rate Limiting
Prevents abuse from specific IPs
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from fastapi import Request, HTTPException, status
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

# In-memory rate limit store (use Redis in production)
# Structure: {ip: {endpoint: [(timestamp, count), ...]}}
rate_limit_store: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
rate_limit_lock = asyncio.Lock()


class IPRateLimiter:
    """IP-based rate limiter for specific endpoints"""

    def __init__(
        self,
        max_requests: int = 10,
        window_hours: int = 1,
        endpoint: str = "default"
    ):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in window
            window_hours: Time window in hours
            endpoint: Endpoint identifier
        """
        self.max_requests = max_requests
        self.window_hours = window_hours
        self.endpoint = endpoint

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        M-23: delegates to the trusted-proxy-aware resolver so this limiter and
        the per-user limiter bucket on the same identity.
        """
        from app.core.client_ip import get_client_ip

        return get_client_ip(request)

    async def check_rate_limit(self, request: Request) -> bool:
        """
        Check if request exceeds rate limit
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if within rate limit
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        client_ip = self._get_client_ip(request)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self.window_hours)

        async with rate_limit_lock:
            # Get request history for this IP and endpoint
            requests = rate_limit_store[client_ip][self.endpoint]

            # Remove old requests outside window
            requests = [
                (timestamp, count) 
                for timestamp, count in requests 
                if timestamp > window_start
            ]

            # Count total requests in window
            total_requests = sum(count for _, count in requests)

            if total_requests >= self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on {self.endpoint}",
                    extra={
                        "client_ip": client_ip,
                        "endpoint": self.endpoint,
                        "requests": total_requests,
                        "limit": self.max_requests
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_hours} hour(s)."
                )

            # Add current request
            requests.append((now, 1))
            rate_limit_store[client_ip][self.endpoint] = requests

            logger.debug(
                f"Rate limit check passed for IP {client_ip} on {self.endpoint}: {total_requests + 1}/{self.max_requests}"
            )
            return True

    async def cleanup_old_entries(self):
        """Clean up old rate limit entries (call periodically)"""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self.window_hours * 2)  # Keep 2x window for safety

        async with rate_limit_lock:
            for ip in list(rate_limit_store.keys()):
                for endpoint in list(rate_limit_store[ip].keys()):
                    requests = rate_limit_store[ip][endpoint]
                    requests = [
                        (timestamp, count) 
                        for timestamp, count in requests 
                        if timestamp > window_start
                    ]

                    if requests:
                        rate_limit_store[ip][endpoint] = requests
                    else:
                        del rate_limit_store[ip][endpoint]

                if not rate_limit_store[ip]:
                    del rate_limit_store[ip]


# Pre-configured rate limiters for different endpoints
booking_rate_limiter = IPRateLimiter(
    max_requests=10,  # 10 bookings per hour per IP
    window_hours=1,
    endpoint="online_booking"
)

auth_rate_limiter = IPRateLimiter(
    max_requests=20,  # 20 login attempts per hour per IP
    window_hours=1,
    endpoint="auth_login"
)

password_reset_rate_limiter = IPRateLimiter(
    max_requests=5,  # 5 password reset requests per hour per IP
    window_hours=1,
    endpoint="password_reset"
)
