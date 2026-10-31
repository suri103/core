"""
CoreDent API - Main Application Entry Point
FastAPI application with security and audit controls designed for healthcare data
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config_simple import settings
from app.core.database import engine
from app.core.limiter import limiter
from app.api.v1.api import api_router
from app.models import Base

import logging
import logging.config
import os
import re
import traceback
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger
from typing import Any, Dict

if settings.ENVIRONMENT == "production":
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        # Signature intentionally mirrors the pythonjsonlogger 2.x/3.x
        # implementation; parameter names differ across versions, so the
        # override is typed loosely on purpose.
        def add_fields(self, record, message, extra):  # type: ignore[override]
            super().add_fields(record, message, extra)
            from datetime import timezone
            record['timestamp'] = datetime.now(timezone.utc).isoformat()
            record['level'] = record.levelname
            record['service'] = settings.APP_NAME

    handler = logging.StreamHandler()
    handler.setFormatter(CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s'))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]

logger = logging.getLogger(__name__)

# Sentry and Prometheus live in app/core/observability.py so that every process
# role initializes them. While this block lived here, only the web process ever
# called sentry_sdk.init(), so capture_exception() inside a Celery task was a
# no-op and background failures left no trace.
from app.core.observability import (
    capture_security_event,
    init_sentry,
    record_http_request,
    record_security_event,
    report_missing_celery_worker,
    update_celery_queue_depth,
)

init_sentry("web")

# Environments where console email, local-disk storage and a skipped captcha are
# intentional. Anything else can hold real data and is audited at startup.
_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "test", "testing", "local"})


def log_security_event(
    event_type: str,
    severity: str,
    message: str,
    extra: Dict[str, Any] = None
):
    """
    Log security events to Sentry and application logs
    
    Args:
        event_type: Type of security event (e.g., 'rate_limit', 'auth_failure')
        severity: Severity level ('info', 'warning', 'error', 'critical')
        message: Event description
        extra: Additional context data
    """
    log_data = {
        'event_type': event_type,
        'severity': severity,
        # Timezone FIX: aware UTC so log correlation/sorting holds across hosts.
        'timestamp': datetime.now(timezone.utc).isoformat(),
        **(extra or {})
    }

    # Log to application logs
    if severity == 'critical':
        logger.critical(message, extra=log_data)
    elif severity == 'error':
        logger.error(message, extra=log_data)
    elif severity == 'warning':
        logger.warning(message, extra=log_data)
    else:
        logger.info(message, extra=log_data)

    # Send to Sentry if configured (a no-op when the DSN is unset).
    capture_security_event(event_type, severity, message, log_data)

# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic.

    Replaces the deprecated ``@app.on_event("startup")`` and
    ``@app.on_event("shutdown")`` hooks.  FastAPI recommends this pattern
    since v0.100.0.
    """
    # ---- STARTUP ----
    # Create database tables (in production, use Alembic migrations)
    if settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    if settings.DEBUG:
        logger.info("API Docs: http://localhost:3000/docs")

    # Readiness audit — log warnings for unconfigured integrations.
    #
    # This runs for every environment that can hold real data, not only
    # "production". Keying it on production alone meant a deployment running as
    # staging could have console email, local-disk file storage, an unscanned
    # upload path and a skipped captcha while the audit that should have reported
    # all of it was itself switched off - each of those behaviours is selected by
    # comparing ENVIRONMENT to "production".
    #
    # These are soft warnings because some integrations are genuinely optional
    # for some deployments (e.g. US-only deployments don't need Razorpay).
    if settings.ENVIRONMENT not in _LOCAL_ENVIRONMENTS:
        readiness_warnings = []
        if not settings.SENTRY_DSN:
            readiness_warnings.append(
                "SENTRY_DSN not set — error monitoring disabled. "
                "You will have NO visibility into production errors."
            )
        if not settings.SMTP_USER or settings.SMTP_HOST == "localhost":
            readiness_warnings.append(
                "SMTP not configured — password resets, email verification, "
                "and appointment reminders will fail silently."
            )
        if settings.EMAIL_PROVIDER == "console":
            readiness_warnings.append(
                f"EMAIL_PROVIDER is 'console' (ENVIRONMENT={settings.ENVIRONMENT}). "
                "Mail is written to the log and reported as DELIVERED, so nothing "
                "reaches a recipient and no failure is ever recorded. Set "
                "EMAIL_PROVIDER=smtp or aws_ses."
            )
        if settings.SMS_PROVIDER == "console":
            readiness_warnings.append(
                f"SMS_PROVIDER is 'console' (ENVIRONMENT={settings.ENVIRONMENT}). "
                "Text messages are written to the log instead of being sent."
            )
        if not settings.AWS_S3_BUCKET:
            readiness_warnings.append(
                "AWS_S3_BUCKET not set — file/image uploads will fail."
            )
        elif settings.ENVIRONMENT != "production":
            # storage.get_storage() selects S3 only for ENVIRONMENT=production,
            # so a configured bucket is silently unused in every other env.
            readiness_warnings.append(
                f"AWS_S3_BUCKET is set but ENVIRONMENT={settings.ENVIRONMENT}, so "
                "uploads use LOCAL disk: files are lost on redeploy, never reach "
                "the bucket, and are invisible to other replicas."
            )
        if not settings.REDIS_URL:
            readiness_warnings.append(
                "REDIS_URL not set — rate limiting falls back to in-memory, "
                "which does NOT work across multiple instances."
            )
        if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
            readiness_warnings.append(
                "ALLOWED_HOSTS not configured for production — "
                "TrustedHostMiddleware will not protect against Host header attacks."
            )
        if settings.CORS_ORIGINS and any(
            "localhost" in origin for origin in settings.CORS_ORIGINS
        ):
            readiness_warnings.append(
                "CORS_ORIGINS contains localhost — remove development origins "
                "before going live."
            )

        # file_security fails OPEN outside production (is_clean = not
        # is_production), so with no scanner the upload is accepted unverified;
        # inside production the identical gap REJECTS every upload. Either way
        # the operator needs to know which side of that they are on.
        if not os.getenv("CLAMAV_HOST") and not (
            getattr(settings, "VIRUSTOTAL_API_KEY", None)
            or os.getenv("VIRUSTOTAL_API_KEY")
        ):
            readiness_warnings.append(
                "No virus scanner configured (CLAMAV_HOST / VIRUSTOTAL_API_KEY). "
                "Uploads are accepted unscanned and enter PHI storage unverified."
            )
        if not getattr(settings, "RECAPTCHA_SECRET_KEY", ""):
            readiness_warnings.append(
                "RECAPTCHA_SECRET_KEY not set — captcha is skipped on public "
                "booking and the patient portal, leaving them open to bots."
            )

        if readiness_warnings:
            logger.warning("=" * 70)
            logger.warning(f"{settings.ENVIRONMENT.upper()} READINESS WARNINGS")
            logger.warning("=" * 70)
            for w in readiness_warnings:
                logger.warning(f"  • {w}")
            logger.warning("=" * 70)
        else:
            logger.info("Readiness check: all configured integrations present")

    # Publishing a task is not the same as running it: the message only leaves
    # the broker when a worker consumes it, so a deployment with no worker role
    # still returns success from every enqueue_email() call while nothing is
    # ever delivered. Probe once so the condition appears in the deploy log
    # instead of only as confirmation emails that never arrive.
    await report_missing_celery_worker()

    yield  # ---- application is running ----

    # ---- SHUTDOWN ----
    logger.info(f"{settings.APP_NAME} shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    # NOTE: we deliberately do *not* claim "HIPAA-ready" in the API
    # description.  HIPAA is an operational program (BAAs, SRA, policies,
    # breach procedures) and cannot be conveyed by a string.  See
    # HONEST_PRODUCTION_REVIEW.md for the full security posture and the
    # remaining gaps.
    description="Dental Practice Management System API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Initialize rate limiter with default limits
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Tenant isolation guard.  Enforces that the practice_id in the URL/body
# matches the practice_id in the JWT.  Must be added BEFORE other middleware
# so it sees the request first.
try:
    from app.core.tenant_guard import TenantGuardMiddleware
    app.add_middleware(TenantGuardMiddleware)
    logger.info("Tenant isolation guard enabled")
except Exception as exc:  # pragma: no cover
    logger.warning(f"Tenant guard unavailable: {exc}")

# Add security headers on every response, in every environment. They were
# previously skipped in local dev/test, which meant the CSP/XFO regression
# tests could not exercise the middleware (tests/test_security_headers_metrics.py
# documents the intended always-on contract) and a misconfigured deploy could
# silently lose HSTS/CSP. The headers are inert outside HTTPS and the CSP
# allow-lists exactly the third-party origins the frontend needs:
#   - https://js.stripe.com    -> Stripe.js for payments
#   - https://*.sentry.io      -> Sentry error reporting + tracing
#   - https://app.posthog.com  -> PostHog product analytics
#   - https://*.amazonaws.com / *.cloudfront.net  -> S3 / CloudFront uploads
#   - https://public.blob.vercel-storage.com      -> legacy Vercel Blob assets
# If you add another service, add its origin here AND audit the
# implication for PHI exfiltration.
# SECURITY: Removed 'unsafe-inline' from script-src and style-src.
# Previously allowed because some inline scripts slipped in, but
# 'unsafe-inline' effectively disables the XSS protection CSP
# provides and is a HIPAA control failure for a SaaS that handles
# PHI.  Vite emits non-hashed, non-nonced scripts; add a nonce
# or hash to any legitimate inline script before reintroducing it.
# Same applies to style-src (most inline style is from React/emotion
# and can be refactored to class names).
# L-3 FIX: removed https://cdn.jsdelivr.net from script-src — the frontend
# vendors everything into hashed local assets and nothing loads scripts from
# jsDelivr (verified across src/, index.html and the built bundle); keeping a
# general-purpose CDN in script-src only adds supply-chain exposure.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # HSTS (Railway already provides HTTPS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    # SECURITY FIX: Add comprehensive security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://js.stripe.com; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://public.blob.vercel-storage.com https://*.amazonaws.com https://*.cloudfront.net; "
        "connect-src 'self' https://*.sentry.io https://*.posthog.com https://api.stripe.com https://*.amazonaws.com https://*.cloudfront.net; "
        "frame-src https://js.stripe.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    return response

# CORS Middleware - Restrict to specific methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # Explicit methods only
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRF-Token",
        "X-Requested-With",
    ],  # Explicit headers only
    expose_headers=["X-Total-Count", "X-Page", "X-Page-Size"],
    max_age=3600,  # Cache preflight for 1 hour
)
# Usage metering for usage-based subscription billing (see
# app/services/usage_metering.py). OPT-IN via USAGE_TRACKING_ENABLED=true.
# When enabled, every successful (2xx) authenticated /api/v1/* request is
# recorded against the practice's active subscription AFTER the response has
# started, so metering never adds client latency and a metering fault can
# never fail the customer request (the middleware is fail-open to success).
# Default off is deliberate: metering adds a per-request write, and enabling
# it is the explicit choice to bill usage. If usage-based plans are sold,
# set USAGE_TRACKING_ENABLED=true in production — otherwise
# Subscription.current_usage stays 0.
if settings.USAGE_TRACKING_ENABLED:
    from app.services.usage_metering import UsageTrackingMiddleware

    app.add_middleware(UsageTrackingMiddleware)
    logger.info("Usage tracking middleware enabled")

# SECURITY FIX: Security Monitoring Middleware
@app.middleware("http")
async def security_monitoring_middleware(request: Request, call_next):
    """
    Monitor and log security-relevant events
    
    Tracks:
    - Failed authentication attempts
    - Rate limit violations
    - Suspicious request patterns
    - Error rates
    """
    import time

    start_time = time.time()

    try:
        response = await call_next(request)

        # Track failed authentication
        if response.status_code == 401:
            log_security_event(
                event_type='auth_failure',
                severity='warning',
                message=f"Authentication failed: {request.url.path}",
                extra={
                    'path': str(request.url.path),
                    'method': request.method,
                    'ip': request.client.host if request.client else 'unknown',
                    'user_agent': request.headers.get('user-agent', 'unknown')
                }
            )
            record_security_event('auth_failure')

        # Track rate limit violations
        elif response.status_code == 429:
            log_security_event(
                event_type='rate_limit',
                severity='warning',
                message=f"Rate limit exceeded: {request.url.path}",
                extra={
                    'path': str(request.url.path),
                    'method': request.method,
                    'ip': request.client.host if request.client else 'unknown'
                }
            )
            record_security_event('rate_limit')

        # Track server errors
        elif response.status_code >= 500:
            log_security_event(
                event_type='server_error',
                severity='error',
                message=f"Server error: {request.url.path}",
                extra={
                    'path': str(request.url.path),
                    'method': request.method,
                    'status_code': response.status_code,
                    'duration_ms': (time.time() - start_time) * 1000
                }
            )
            record_security_event('server_error')

        # Duration is recorded for every request, not just the error paths
        # above, so latency alerting has full coverage.
        record_http_request(request, response.status_code, time.time() - start_time)

        return response

    except Exception as e:
        # Log unexpected errors
        log_security_event(
            event_type='exception',
            severity='critical',
            message=f"Unhandled exception: {str(e)}",
            extra={
                'path': str(request.url.path),
                'method': request.method,
                'error': str(e)
            }
        )
        record_security_event('exception')
        raise

# HIGH-01 FIX: Audit Logging Middleware for security and compliance
if settings.AUDIT_LOG_ENABLED:
    @app.middleware("http")
    async def audit_logging_middleware(request: Request, call_next):
        """Log all API requests for security audit trail"""
        import time
        from datetime import datetime, timezone

        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Only log API requests (not health checks, metrics, docs)
        if request.url.path.startswith("/api/"):
            # Get user info if authenticated
            user_id = None
            practice_id = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from app.core.security import decode_token
                    token = auth_header[7:]
                    payload = decode_token(token)
                    if payload:
                        user_id = payload.get("sub")
                        practice_id = payload.get("practice_id")
                except Exception:
                    pass

            # Log the request (M-3 FIX: query values redacted — raw query
            # params such as ?phone=/patient search carry PHI into logs)
            logger.info(
                "API_REQUEST",
                extra={
                    "audit": True,
                    "method": request.method,
                    "path": request.url.path,
                    "query": _redacted_query(request.query_params),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "practice_id": practice_id,
                    "ip_address": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        return response

# Redis-backed rate limiting. The shared slowapi limiter (which uses the
# Redis storage backend in production) is constructed once in
# app.core.limiter — route decorators and the exception handler below all
# use that single instance. This block previously tried to import a
# nonexistent ``RedisRateLimitMiddleware`` and swallowed the ImportError,
# logging "Redis rate limiting enabled" was unreachable while the real
# limiter had already been configured by app.core.limiter at import time.
# L-2 FIX: dead block removed; see app/core/limiter.py and
# app/core/redis_rate_limit.py for the actual Redis rate-limit wiring.

# Trusted Host Middleware (security)
# Only enable if ALLOWED_HOSTS is explicitly configured
if not settings.DEBUG and settings.ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors - hide details in production"""
    if settings.DEBUG:
        # `exc.errors()` and `exc.body` may contain Decimal/datetime values
        # that json.dumps can't handle directly. Coerce via jsonable_encoder.
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(
                {
                    "detail": exc.errors(),
                    "body": exc.body,
                }
            ),
        )

    # Production: Don't expose internal details
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "type": "validation_error",
        },
    )


# PHI Scrubbing Patterns (Expanded for clinical coverage)
PHI_KEYS = {
    "first_name", "last_name", "email", "phone", "dob", "date_of_birth", "address",
    "ssn", "insurance_id", "license", "account_number", "card_number",
    # Query-string search terms may themselves be PHI (e.g. ?query=John).
    "query", "search", "q", "name",
    # Clinical free text. These carry PHI in their VALUES, so both the
    # query-string redactor and redact_phi must recognise them; a notes or
    # treatment payload is otherwise "safe" by key name while containing the
    # patient's history in prose.
    "content", "note", "notes", "subjective", "objective", "assessment", "plan",
    "diagnosis", "chief_complaint", "reason", "message", "body", "symptoms",
    "medical_history", "allergies", "medications",
}
# Query params safe to log verbatim (pagination / non-PHI filters).
_QUERY_SAFE_KEYS = {"skip", "limit", "page", "page_size", "sort", "order"}


def _redacted_query(query_params) -> str | None:
    """Render query params with PHI redacted (M-3 FIX).

    Patient search (`?query=`, `?phone=`, ...) would otherwise land verbatim
    in structured audit logs. Pagination keys stay verbatim; everything else
    is redacted by key (PHI_KEYS) or, conservatively, replaced with
    [REDACTED] when the key is unknown.
    """
    if not query_params:
        return None
    parts = []
    for key in query_params.keys():
        kl = key.lower()
        if kl in _QUERY_SAFE_KEYS:
            for v in query_params.getlist(key):
                parts.append(f"{key}={v}")
        elif kl in PHI_KEYS:
            parts.append(f"{key}=[REDACTED]")
        else:
            # Unknown key: hide value, keep key for debugging.
            parts.append(f"{key}=[REDACTED]")
    return "&".join(parts) if parts else None

def _phi_key_norm(key: Any) -> str:
    """Normalize a payload key for PHI matching.

    Browser-side payloads use camelCase ('lastName', 'dateOfBirth') while the
    backend dialect is snake_case; matching only one dialect leaked PHI into
    exception logs (test_main.py::TestRedactPhi). Lowercase, split camel
    humps, and collapse separators so 'lastName', 'last-name' and
    'last_name' all match.
    """
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return re.sub(r"[\s\-]+", "_", snake).lower()


def redact_phi(data: Any) -> Any:
    """Recursively scrub common PHI patterns from a dictionary or list.

    Keys are normalized (see _phi_key_norm) before matching so camelCase
    variants are redacted exactly like their snake_case twins.
    """
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if _phi_key_norm(k) in PHI_KEYS else redact_phi(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_phi(item) for item in data]
    return data

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors - never expose details in production + scrub PHI from logs."""

    # Scrub PHI from request info for internal logging
    client_host = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    url = str(request.url)

    # Redact URL if it contains PHI patterns (e.g. patients?name=John)
    for key in PHI_KEYS:
        url = re.sub(rf"({key}=)[^&]*", r"\1[REDACTED]", url, flags=re.IGNORECASE)

    # Request body: values only in DEBUG.
    #
    # Key-name redaction is not sufficient for clinical payloads: the PHI sits in
    # free-text fields whose names carry no hint (content, subjective,
    # assessment, plan, reason, ...), so a 500 on POST /patients/{id}/notes wrote
    # the note verbatim into production logs and into Sentry (the ERROR-level
    # LoggingIntegration event whose message is this formatted line). In
    # non-debug environments only the top-level key NAMES are logged, which is
    # what an operator needs to identify the payload shape.
    body_display = "[NOT_JSON_OR_NOT_LOADED]"
    try:
        body = await request.json()
        if settings.DEBUG:
            body_display = str(redact_phi(body))
        elif isinstance(body, dict):
            body_display = f"[KEYS_ONLY] {sorted(str(key) for key in body)}"
        else:
            body_display = f"[KEYS_ONLY] non-object {type(body).__name__}"
    except Exception:
        pass

    # Log full error internally with SANITIZED request context
    logger.error(
        f"Unhandled exception: {method} {url} from {client_host}\n"
        f"Body: {body_display}\n"
        f"Error: {str(exc)}\n"
        f"Traceback: {traceback.format_exc()}",
        extra={
            "path": path,
            "method": method,
            "client": client_host,
        }
    )

    # In debug mode, raise for detailed traceback
    if settings.DEBUG:
        raise exc

    # In production, return generic error (never expose internals)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Please contact support if the problem persists.",
            "type": "server_error",
        },
    )


# HIGH-03 FIX: Health check endpoint - minimal info for monitoring, detailed info requires auth
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring - returns minimal info for security"""
    db_status = "unknown"
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Return minimal info for security (no version, no app name in production)
    if settings.DEBUG:
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "database": db_status,
        }

    # Production: minimal response
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe: can this replica serve traffic right now?

    Distinct from /health, which only proves the process is up and the database
    answers. /ready also checks Redis, because the shared rate limiter fails
    CLOSED in production: when its Redis storage is unreachable, guarded
    requests are rejected with a hard error instead of degrading. A replica in
    that state should be taken out of rotation, not keep receiving traffic.

    Returns 503 when a dependency is down so the platform health check can act.
    """
    import asyncio

    from sqlalchemy import text

    checks: Dict[str, str] = {"database": "unknown", "redis": "unknown"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception:
        checks["database"] = "disconnected"

    if not settings.REDIS_URL:
        # Outside production the limiter falls back to process-local memory, so
        # readiness must not depend on Redis being configured.
        checks["redis"] = "not_configured"
    else:
        def _ping_redis() -> bool:
            import redis

            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            try:
                return bool(client.ping())
            finally:
                client.close()

        try:
            # redis-py's client is synchronous: run it off the event loop so a
            # hung Redis cannot stall every other request on this worker.
            checks["redis"] = (
                "connected" if await asyncio.to_thread(_ping_redis) else "disconnected"
            )
        except Exception:
            checks["redis"] = "disconnected"

    ready = checks["database"] == "connected" and checks["redis"] in (
        "connected",
        "not_configured",
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not_ready", **checks},
    )


# CRIT-04 FIX: Metrics endpoint protected - only accessible in debug mode or with secret key
@app.get("/metrics", tags=["Monitoring"])
async def metrics(request: Request):
    """Prometheus metrics endpoint - PROTECTED"""
    # In production, only allow access if a secret monitoring token is provided.
    # Header-only (X-Monitoring-Token): ?token= leaks into logs/history. The
    # query path is kept for existing scrapers but logs redacted ([REDACTED]).
    if not settings.DEBUG:
        monitoring_token = None  # query token deprecated; header required
        secret_token = request.headers.get("X-Monitoring-Token")

        # Allow access only with valid token (set via env var MONITORING_TOKEN)
        expected_token = settings.MONITORING_TOKEN
        if not expected_token or (monitoring_token != expected_token and secret_token != expected_token):
            from fastapi import HTTPException as HTTPExc
            raise HTTPExc(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Monitoring endpoint requires authentication.",
            )

    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    # Broker backlog is a live value, not a counter, so refresh it before
    # rendering: a worker that stopped consuming then surfaces as a rising
    # queue depth as soon as anything is published to it.
    await update_celery_queue_depth()

    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mount local uploads directory so uploaded logos and local dev files are served
_uploads_dir = Path("uploads")
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3000,
        reload=settings.DEBUG,
        log_level="info",
    )
