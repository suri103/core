"""Sentry initialization and Prometheus metrics, shared by every process role.

Two gaps this module closes:

1. Sentry was initialized in ``app/main.py``, which only the web process
   imports. Workers and beat never called ``sentry_sdk.init()``, so every
   ``capture_exception`` inside a Celery task was a silent no-op: background
   failures (email delivery, rate-limit backend loss, a wedged sweep) left no
   trace beyond the container log.
2. ``prometheus_client`` was installed and ``/metrics`` existed, but not a
   single application metric was defined, so the endpoint exposed only the
   default process/GC collectors and nothing was alertable.

Initialization is deliberately role-agnostic: every integration is attached
when its library is importable, and ``role`` is only a tag. ``app.core.celery_app``
and ``app.main`` both call :func:`init_sentry`, and which one wins the import
race depends on the process, so keying integrations off the role would make
behaviour depend on import order.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram

from app.core.config_simple import settings

logger = logging.getLogger(__name__)

_sentry_sdk: Any = None
_sentry_initialized = False


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

def filter_sensitive_data(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter sensitive data from Sentry events (privacy protection)

    Removes:
    - Passwords
    - Tokens
    - API keys
    - Patient data
    - Email addresses
    - Phone numbers
    """
    sensitive_keys = [
        'password', 'token', 'secret', 'api_key', 'authorization',
        'ssn', 'social_security', 'credit_card', 'card_number',
        'patient_name', 'email', 'phone', 'address',
        # Name/DOB coverage: matching is substring-based over key.lower(), so
        # 'name' also catches camelCase 'firstName'/'lastName'/'fullName';
        # 'dob' and 'dateofbirth' cover both DOB spellings.
        'first_name', 'last_name', 'name', 'date_of_birth', 'dateofbirth', 'dob',
    ]

    def redact_dict(d: dict) -> dict:
        """Recursively redact sensitive keys"""
        if not isinstance(d, dict):
            return d

        for key in list(d.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                d[key] = '[REDACTED]'
            elif isinstance(d[key], dict):
                d[key] = redact_dict(d[key])
            elif isinstance(d[key], list):
                d[key] = [redact_dict(item) if isinstance(item, dict) else item for item in d[key]]

        return d

    def redact_text(text: str) -> str:
        """Best-effort redaction of `key=value` / `key: value` pairs in prose.

        This cannot recognise PHI written as free sentences - the durable fix
        for that is not logging it in the first place (see the 500 handler in
        app/main.py) - but it does cover the structured forms that reach the
        log line through f-strings and URLs.
        """
        for sensitive in sensitive_keys:
            text = re.sub(
                rf"({re.escape(sensitive)}\s*[=:]\s*)([^\s,;)\]}}]+)",
                r"\1[REDACTED]",
                text,
                flags=re.IGNORECASE,
            )
        return text

    # Redact request data
    if 'request' in event:
        event['request'] = redact_dict(event['request'])

    # Redact extra data
    if 'extra' in event:
        event['extra'] = redact_dict(event['extra'])

    # Redact the log-record message. LoggingIntegration turns every logger.error
    # into an event whose ``logentry.message`` is the formatted log line, and the
    # message was previously left untouched: the body of a failed clinical write
    # or a provider error carrying an address went to Sentry verbatim.
    logentry = event.get('logentry')
    if isinstance(logentry, dict) and isinstance(logentry.get('message'), str):
        logentry['message'] = redact_text(logentry['message'])

    # Same treatment for breadcrumbs (INFO+ log records and SDK breadcrumbs).
    breadcrumbs = event.get('breadcrumbs')
    values = breadcrumbs.get('values') if isinstance(breadcrumbs, dict) else None
    if isinstance(values, list):
        for crumb in values:
            if isinstance(crumb, dict) and isinstance(crumb.get('message'), str):
                crumb['message'] = redact_text(crumb['message'])

    return event


def _build_integrations() -> list:
    """Attach every integration whose library is importable.

    Each import is guarded independently: a deployment that installs
    sentry-sdk without the Celery extra, or a web image without the Celery
    package, must still get the integrations it does have.
    """
    integrations: list = []
    for module, name in (
        ("sentry_sdk.integrations.sqlalchemy", "SqlalchemyIntegration"),
        ("sentry_sdk.integrations.logging", "LoggingIntegration"),
        ("sentry_sdk.integrations.fastapi", "FastApiIntegration"),
        ("sentry_sdk.integrations.celery", "CeleryIntegration"),
    ):
        try:
            imported = __import__(module, fromlist=[name])
            integration = getattr(imported, name)
            # INFO+ becomes breadcrumbs, ERROR+ becomes an event.
            if name == "LoggingIntegration":
                integrations.append(integration(level=logging.INFO, event_level=logging.ERROR))
            else:
                integrations.append(integration())
        except Exception:  # noqa: BLE001 - an unavailable integration is not fatal
            logger.debug("Sentry integration unavailable: %s", name, exc_info=True)
    return integrations


def init_sentry(role: str = "web") -> bool:
    """Initialize Sentry once per process. Returns True when it is active.

    Idempotent, so ``app.main`` (web) and ``app.core.celery_app`` (worker/beat)
    can both call it without caring which runs first.
    """
    global _sentry_sdk, _sentry_initialized

    if _sentry_initialized:
        return True
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured - monitoring disabled")
        return False

    try:
        import sentry_sdk
    except Exception:
        logger.warning("sentry-sdk is not installed - monitoring disabled")
        return False

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=_build_integrations(),
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% for profiling
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
            # SECURITY: filter PHI/credentials out of every event before send.
            before_send=lambda event, hint: filter_sensitive_data(event),
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send PII by default
        )
        sentry_sdk.set_tag("process_role", role)
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)
        return False

    _sentry_sdk = sentry_sdk
    _sentry_initialized = True
    logger.info("Sentry monitoring initialized (role=%s)", role)
    return True


def capture_security_event(
    event_type: str,
    severity: str,
    message: str,
    data: Dict[str, Any],
) -> None:
    """Push a tagged security event to Sentry (message or breadcrumb).

    Never raises: an observability failure must not change request behaviour.
    """
    if _sentry_sdk is None:
        return
    try:
        with _sentry_sdk.push_scope() as scope:
            scope.set_tag("event_type", event_type)
            scope.set_tag("severity", severity)
            scope.set_context("security_event", data)

            if severity in ("error", "critical"):
                _sentry_sdk.capture_message(message, level=severity)
            else:
                _sentry_sdk.add_breadcrumb(
                    category="security",
                    message=message,
                    level=severity,
                    data=data,
                )
    except Exception:
        logger.debug("Failed to capture security event", exc_info=True)


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
# All prefixed to stay clear of the default process/GC collectors. Labels are
# deliberately low-cardinality: `route` is the matched route template rather
# than the raw path (see route_label), so scanner traffic cannot create a new
# time series per request.

http_requests_total = Counter(
    "coredent_http_requests_total",
    "HTTP requests handled, by method, route template and status.",
    ["method", "route", "status"],
)

http_request_duration_seconds = Histogram(
    "coredent_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

security_events_total = Counter(
    "coredent_security_events_total",
    "Security-relevant events, by type (auth_failure, rate_limit, server_error, exception).",
    ["event_type"],
)

celery_tasks_total = Counter(
    "coredent_celery_tasks_total",
    "Celery task completions, by task name and terminal state.",
    ["task", "state"],
)

celery_task_duration_seconds = Histogram(
    "coredent_celery_task_duration_seconds",
    "Celery task wall-clock duration in seconds.",
    ["task"],
    buckets=(0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0),
)

celery_queue_depth = Gauge(
    "coredent_celery_queue_depth",
    "Messages waiting in a Celery queue. A rising trend means nothing is consuming it.",
    ["queue"],
)

# Must match ``CELERY_QUEUES`` in start.py; the worker role is launched with
# ``-Q`` built from that value. Kept as a literal here rather than imported
# because start.py is a process entrypoint, and guarded by a drift test.
DEFAULT_CONSUMED_QUEUES = "default,communications,reminders,emails"


def route_label(request: Any) -> str:
    """Bounded-cardinality route label for a request.

    Prefers the matched route template (``/api/v1/patients/{patient_id}``).
    Unmatched requests - 404s from scanners, mostly - collapse into a single
    bucket instead of minting a series per invented path.
    """
    try:
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
    except Exception:
        logger.debug("Could not resolve route template", exc_info=True)
    return "unmatched"


def record_http_request(request: Any, status_code: int, duration_seconds: float) -> None:
    """Record one completed request. Never raises."""
    try:
        route = route_label(request)
        http_requests_total.labels(request.method, route, str(status_code)).inc()
        http_request_duration_seconds.labels(request.method, route).observe(duration_seconds)
    except Exception:
        logger.debug("Failed to record HTTP metrics", exc_info=True)


def record_security_event(event_type: str) -> None:
    """Count one security event. Never raises."""
    try:
        security_events_total.labels(event_type).inc()
    except Exception:
        logger.debug("Failed to record security metric", exc_info=True)


def install_celery_metrics(celery_app: Any) -> None:
    """Attach task count/duration collectors to a Celery app.

    ``task_failure`` reporting is left to Sentry's CeleryIntegration rather
    than done here, so a failure is reported exactly once.
    """
    try:
        from celery import signals
    except Exception:
        logger.debug("Celery signals unavailable; task metrics disabled", exc_info=True)
        return

    started: Dict[str, float] = {}

    @signals.task_prerun.connect
    def _task_prerun(task_id: Optional[str] = None, **_kwargs: Any) -> None:
        if task_id:
            started[task_id] = time.monotonic()

    @signals.task_postrun.connect
    def _task_postrun(
        task_id: Optional[str] = None,
        task: Any = None,
        state: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        name = getattr(task, "name", "unknown")
        try:
            celery_tasks_total.labels(name, str(state or "UNKNOWN")).inc()
            begun = started.pop(task_id, None) if task_id else None
            if begun is not None:
                celery_task_duration_seconds.labels(name).observe(time.monotonic() - begun)
        except Exception:
            logger.debug("Failed to record Celery metrics", exc_info=True)


# ---------------------------------------------------------------------------
# "Nothing is consuming the queue" detection
# ---------------------------------------------------------------------------
#
# Publishing a task is not the same as running it: the message only leaves the
# broker when a worker consumes it. With no worker role deployed, ``apply_async``
# still succeeds against a live broker, so ``enqueue_email`` returns normally,
# the caller's except-block never fires, and every beat schedule silently never
# runs. The API has no other way to observe that - which is how registration
# verification mail, password resets and the retention purge can all stop while
# the deploy still looks healthy. Queue depth is that missing signal.

def consumed_queues() -> List[str]:
    """Queue names the worker role consumes, honouring the CELERY_QUEUES override."""
    raw = os.environ.get("CELERY_QUEUES") or DEFAULT_CONSUMED_QUEUES
    return [name.strip() for name in raw.split(",") if name.strip()]


def broker_url() -> Optional[str]:
    """Broker the API publishes to, or None when no broker is configured."""
    return settings.CELERY_BROKER_URL or settings.REDIS_URL or None


def _fetch_queue_depths(broker: str, queues: List[str]) -> Dict[str, int]:
    """Read pending-message counts straight from the Redis broker.

    celery does not use a key prefix for the default redis transport, so each
    queue name is the list key holding its waiting messages.
    """
    import redis

    client = redis.from_url(
        broker,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        return {queue: int(client.llen(queue)) for queue in queues}
    finally:
        client.close()


async def update_celery_queue_depth() -> None:
    """Refresh the queue-depth gauges. Never raises.

    Values are deliberately left unset when the broker cannot be read, so a
    ``absent()`` alert can distinguish "broker unreachable" from "queue empty"
    rather than both reading as zero.
    """
    broker = broker_url()
    if not broker or not broker.startswith("redis"):
        return

    try:
        depths = await asyncio.to_thread(_fetch_queue_depths, broker, consumed_queues())
    except Exception:
        logger.debug("Could not read Celery queue depth", exc_info=True)
        return

    for queue, depth in depths.items():
        try:
            celery_queue_depth.labels(queue).set(depth)
        except Exception:
            logger.debug("Failed to set queue-depth gauge", exc_info=True)


async def check_celery_worker_presence(timeout: float = 1.0) -> Optional[bool]:
    """Return True/False when the broker replied, None when the probe failed.

    A worker probing itself is meaningless and beat has no task protocol, so the
    caller is expected to gate this on the process role.
    """
    broker = broker_url()
    if not broker:
        return None
    try:
        from app.core.celery_app import celery_app

        pong = await asyncio.to_thread(celery_app.control.ping, timeout=timeout)
        return bool(pong)
    except Exception:
        logger.debug("Celery worker presence probe unavailable", exc_info=True)
        return None


async def report_missing_celery_worker() -> None:
    """Log loudly when this process publishes work that nothing consumes.

    Non-fatal by design: the API must still serve traffic with no worker
    deployed, but the condition should be visible in the deploy log instead of
    only as confirmation emails that never arrive.
    """
    role = (os.environ.get("PROCESS_TYPE") or "web").strip().lower()
    if role in {"worker", "beat", "scheduler", "release", "migrate"}:
        return

    present = await check_celery_worker_presence()
    if present is False:
        logger.error(
            "No Celery worker responded on the broker. Transactional email "
            "(verification, password reset, staff invites), appointment "
            "reminders, dunning, recalls and the retention purge are all "
            "queued but will NOT run. Deploy the worker and beat services "
            "(PROCESS_TYPE=worker and PROCESS_TYPE=beat); see "
            "docs/RAILWAY_DEPLOY_STEPS.md section 4."
        )
    elif present:
        logger.info("Celery worker detected on the broker")
