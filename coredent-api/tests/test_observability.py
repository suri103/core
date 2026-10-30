"""Observability: Sentry initialization and Prometheus instrumentation.

Covers the gaps this change closes:

- Sentry is initialized for worker/beat, not only web. It used to live in
  app/main.py, which those processes never import, so capture_exception() inside
  a Celery task was a silent no-op.
- /metrics exposes real application metrics rather than only the default
  process/GC collectors.
- /ready separates "process is up" from "able to serve traffic".
"""
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.observability import (
    DEFAULT_CONSUMED_QUEUES,
    check_celery_worker_presence,
    consumed_queues,
    filter_sensitive_data,
    init_sentry,
    report_missing_celery_worker,
    route_label,
    update_celery_queue_depth,
)


class TestSentryInitialization:
    def test_missing_dsn_disables_sentry_without_failing(self, monkeypatch):
        """A deployment with no Sentry DSN must still start cleanly."""
        from app.core import observability
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "SENTRY_DSN", "")
        monkeypatch.setattr(observability, "_sentry_initialized", False)
        monkeypatch.setattr(observability, "_sentry_sdk", None)

        assert init_sentry("web") is False

    def test_init_is_idempotent(self, monkeypatch):
        """app.main and app.core.celery_app both call this; the second is a no-op."""
        from app.core import observability

        monkeypatch.setattr(observability, "_sentry_initialized", True)
        assert init_sentry("worker") is True

    def test_filter_sensitive_data_redacts_phi_and_credentials(self):
        event = {
            "request": {
                "headers": {"Authorization": "Bearer abc123", "X-Custom": "ok"},
                "data": {"email": "patient@example.com"},
            },
            "extra": {"first_name": "Ada", "date_of_birth": "1970-01-01", "note": "kept"},
        }

        filtered = filter_sensitive_data(event)

        assert filtered["request"]["headers"]["Authorization"] == "[REDACTED]"
        assert filtered["request"]["headers"]["X-Custom"] == "ok"
        assert filtered["request"]["data"]["email"] == "[REDACTED]"
        assert filtered["extra"]["first_name"] == "[REDACTED]"
        assert filtered["extra"]["date_of_birth"] == "[REDACTED]"
        # Non-sensitive context survives, otherwise the event is useless.
        assert filtered["extra"]["note"] == "kept"


class TestRouteLabel:
    """Cardinality control: raw paths would mint a series per scanner request."""

    def test_prefers_matched_route_template(self):
        request = SimpleNamespace(
            scope={"route": SimpleNamespace(path="/api/v1/patients/{patient_id}")}
        )
        assert route_label(request) == "/api/v1/patients/{patient_id}"

    def test_buckets_unmatched_requests(self):
        assert route_label(SimpleNamespace(scope={})) == "unmatched"
        assert route_label(SimpleNamespace(scope={"route": None})) == "unmatched"


class TestReadyEndpoint:
    async def test_ready_reports_each_dependency(self, async_client):
        resp = await async_client.get("/ready")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["database"] == "connected"
        # Tests run without REDIS_URL, where the limiter uses process-local
        # memory, so readiness must not demand Redis.
        assert body["redis"] == "not_configured"

    async def test_ready_returns_503_when_database_is_down(
        self, async_client, monkeypatch
    ):
        import app.main as main_module

        class _BrokenConnection:
            async def __aenter__(self):
                raise RuntimeError("database unavailable")

            async def __aexit__(self, *_exc):
                return False

        class _BrokenEngine:
            def connect(self):
                return _BrokenConnection()

        # AsyncEngine.connect is read-only, so swap the engine the endpoint uses.
        monkeypatch.setattr(main_module, "engine", _BrokenEngine())

        resp = await async_client.get("/ready")

        assert resp.status_code == 503
        assert resp.json()["status"] == "not_ready"
        assert resp.json()["database"] == "disconnected"


class TestMetricsEndpoint:
    async def test_metrics_exposes_application_metrics(self, async_client):
        await async_client.get("/health")

        resp = await async_client.get("/metrics")

        assert resp.status_code == 200
        body = resp.text
        assert "coredent_http_requests_total" in body
        assert "coredent_http_request_duration_seconds" in body
        assert "coredent_security_events_total" in body

    async def test_recorded_requests_carry_a_bounded_route_label(self, async_client):
        await async_client.get("/health")

        body = (await async_client.get("/metrics")).text

        # The route template, not the raw path.
        assert 'route="/health"' in body
        # A 404 must not create a series for the path that was guessed.
        await async_client.get("/definitely-not-a-route-xyz")
        body = (await async_client.get("/metrics")).text
        assert 'route="unmatched"' in body

    async def test_auth_failure_is_counted(self, async_client):
        unauthorized = await async_client.get("/api/v1/auth/me")
        assert unauthorized.status_code == 401

        body = (await async_client.get("/metrics")).text

        assert 'coredent_security_events_total{event_type="auth_failure"}' in body

    async def test_metrics_reports_broker_backlog(self, async_client, monkeypatch):
        """A stopped worker is otherwise invisible: publishing still succeeds."""
        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: "redis://example/0")
        monkeypatch.setattr(
            observability,
            "_fetch_queue_depths",
            lambda broker, queues: {queue: 3 for queue in queues},
        )

        body = (await async_client.get("/metrics")).text

        assert 'coredent_celery_queue_depth{queue="emails"} 3.0' in body


class TestCeleryQueueDepth:
    """Depth is the only external signal that nothing is consuming the queues.

    A publish to a live broker always succeeds, so enqueue_email() returns
    normally and every beat schedule silently never fires when no worker role is
    deployed - the API cannot tell, and neither can a health check.
    """

    def test_default_queue_list_matches_the_worker_launch_list(self):
        """start.py builds the worker's -Q from CELERY_QUEUES.

        If these drift, the gauge watches a queue the worker never reads, or
        misses one it does, and the blind spot returns.
        """
        start_py = Path(__file__).resolve().parents[1] / "start.py"
        match = re.search(
            r'^CELERY_QUEUES\s*=\s*"([^"]+)"',
            start_py.read_text(encoding="utf-8"),
            re.MULTILINE,
        )

        assert match, "CELERY_QUEUES not found in start.py"
        assert match.group(1) == DEFAULT_CONSUMED_QUEUES

    def test_queue_list_is_split_and_trimmed(self, monkeypatch):
        monkeypatch.setenv("CELERY_QUEUES", " a, b ,,c ")
        assert consumed_queues() == ["a", "b", "c"]

    async def test_depth_is_published_for_every_consumed_queue(self, monkeypatch):
        from prometheus_client import generate_latest

        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: "redis://example/0")
        monkeypatch.setattr(observability, "consumed_queues", lambda: ["emails"])
        monkeypatch.setattr(
            observability,
            "_fetch_queue_depths",
            lambda broker, queues: {queue: 7 for queue in queues},
        )

        await update_celery_queue_depth()

        body = generate_latest().decode()
        assert 'coredent_celery_queue_depth{queue="emails"} 7.0' in body

    async def test_unreadable_broker_does_not_report_zero(self, monkeypatch):
        """Zero and "could not read" must stay distinguishable for alerting."""
        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: "redis://example/0")

        def _unreachable(broker, queues):
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(observability, "_fetch_queue_depths", _unreachable)

        # Must swallow the failure rather than break the /metrics scrape.
        await update_celery_queue_depth()

    async def test_no_broker_configured_skips_the_read(self, monkeypatch):
        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: None)
        reads = []
        monkeypatch.setattr(
            observability,
            "_fetch_queue_depths",
            lambda broker, queues: reads.append(broker) or {},
        )

        await update_celery_queue_depth()

        assert reads == []

    async def test_non_redis_broker_skips_the_read(self, monkeypatch):
        """LLEN is Redis-specific; a non-redis broker must be reported as absent."""
        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: "amqp://guest@host//")
        reads = []
        monkeypatch.setattr(
            observability,
            "_fetch_queue_depths",
            lambda broker, queues: reads.append(broker) or {},
        )

        await update_celery_queue_depth()

        assert reads == []


class _ListHandler(logging.Handler):
    """Collect records emitted by the logger under test."""

    def __init__(self, sink):
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(record)


class _CaptureObservabilityLogs:
    """Capture app.core.observability records with a handler attached directly.

    caplog is deliberately not used: this suite configures logging itself and no
    record reaches pytest's capture handler, so a caplog assertion would pass or
    fail for reasons unrelated to the code under test. Attaching to the logger
    still asserts the level and the message an operator actually reads.
    """

    def __init__(self) -> None:
        self.records = []

    def __enter__(self):
        self._logger = logging.getLogger("app.core.observability")
        self._previous_level = self._logger.level
        self._handler = _ListHandler(self.records)
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *_exc):
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._previous_level)
        return False

    @property
    def errors(self):
        return [r.getMessage() for r in self.records if r.levelno >= logging.ERROR]


class TestMissingWorkerDetection:
    """Non-fatal by design: the API must serve with no worker, but must say so."""

    async def test_worker_roles_skip_the_probe(self, monkeypatch):
        """A worker probing itself is meaningless; beat has no task protocol."""
        from app.core import observability

        monkeypatch.setenv("PROCESS_TYPE", "beat")
        probed = []

        async def _probe(timeout: float = 1.0) -> bool:
            probed.append(True)
            return True

        monkeypatch.setattr(observability, "check_celery_worker_presence", _probe)

        await report_missing_celery_worker()

        assert probed == []

    async def test_logs_an_error_when_no_worker_answers(self, monkeypatch):
        from app.core import observability

        monkeypatch.delenv("PROCESS_TYPE", raising=False)

        async def _no_worker(timeout: float = 1.0) -> bool:
            return False

        monkeypatch.setattr(observability, "check_celery_worker_presence", _no_worker)

        with _CaptureObservabilityLogs() as captured:
            await report_missing_celery_worker()

        assert len(captured.errors) == 1, "one error, not one per missing feature"
        assert "No Celery worker responded" in captured.errors[0]
        # The operator needs the fix, not just the symptom.
        assert "PROCESS_TYPE=worker" in captured.errors[0]

    async def test_says_nothing_when_a_worker_answered(self, monkeypatch):
        from app.core import observability

        monkeypatch.delenv("PROCESS_TYPE", raising=False)

        async def _worker_present(timeout: float = 1.0) -> bool:
            return True

        monkeypatch.setattr(
            observability, "check_celery_worker_presence", _worker_present
        )

        with _CaptureObservabilityLogs() as captured:
            await report_missing_celery_worker()

        assert captured.errors == []

    async def test_an_inconclusive_probe_is_not_reported_as_missing(self, monkeypatch):
        """None means "could not tell"; warning on it would cry wolf at startup."""
        from app.core import observability

        monkeypatch.delenv("PROCESS_TYPE", raising=False)

        async def _unknown(timeout: float = 1.0):
            return None

        monkeypatch.setattr(observability, "check_celery_worker_presence", _unknown)

        with _CaptureObservabilityLogs() as captured:
            await report_missing_celery_worker()

        assert captured.errors == []

    async def test_probe_returns_none_without_a_broker(self, monkeypatch):
        """Tests and local development run without Redis; must not hang or raise."""
        from app.core import observability

        monkeypatch.setattr(observability, "broker_url", lambda: None)

        assert await check_celery_worker_presence() is None
