"""Startup readiness audit: unconfigured integrations that fail silently.

Every behaviour checked here is selected by comparing ENVIRONMENT to
"production", so a deployment running as anything else can have console email,
local-disk storage, an unscanned upload path and a skipped captcha while the
audit that should report them stays silent. The audit therefore runs for every
environment that can hold real data.
"""
import logging

import pytest


class _ListHandler(logging.Handler):
    def __init__(self, sink):
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(record.getMessage())


class _CaptureMainLogs:
    """Attach to app.main's logger directly; caplog captures nothing here."""

    def __init__(self) -> None:
        self.messages = []

    def __enter__(self):
        self._logger = logging.getLogger("app.main")
        self._previous_level = self._logger.level
        self._handler = _ListHandler(self.messages)
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *_exc):
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._previous_level)
        return False


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """Keep the worker-presence probe out of this file.

    It is covered in test_observability.py and would otherwise attempt a real
    broker connection while these tests drive startup.
    """
    from app.core import observability

    monkeypatch.setattr(observability, "broker_url", lambda: None)


async def _run_startup():
    """Drive the real lifespan. Safe: DEBUG is off, so no DB access occurs."""
    import app.main as main_module

    async with main_module.lifespan(main_module.app):
        pass


class TestReadinessAudit:
    async def test_reports_console_email_which_reports_delivered(self, monkeypatch):
        """The dangerous one: console mail returns success, so nothing is raised."""
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")

        with _CaptureMainLogs() as captured:
            await _run_startup()

        text = "\n".join(captured.messages)
        assert "EMAIL_PROVIDER is 'console'" in text
        assert "reported as DELIVERED" in text

    async def test_reports_local_storage_despite_a_configured_bucket(
        self, monkeypatch
    ):
        """storage.get_storage() only selects S3 for ENVIRONMENT=production."""
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "coredent-staging-bucket")

        with _CaptureMainLogs() as captured:
            await _run_startup()

        text = "\n".join(captured.messages)
        assert "uploads use LOCAL disk" in text

    async def test_reports_unscanned_uploads_and_skipped_captcha(self, monkeypatch):
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        monkeypatch.delenv("CLAMAV_HOST", raising=False)
        monkeypatch.delenv("VIRUSTOTAL_API_KEY", raising=False)
        monkeypatch.setattr(settings, "RECAPTCHA_SECRET_KEY", "")

        with _CaptureMainLogs() as captured:
            await _run_startup()

        text = "\n".join(captured.messages)
        assert "No virus scanner configured" in text
        assert "RECAPTCHA_SECRET_KEY not set" in text

    async def test_skipped_entirely_for_local_environments(self, monkeypatch):
        """Console email and local disk are intentional in development."""
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "test")
        monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")

        with _CaptureMainLogs() as captured:
            await _run_startup()

        assert "READINESS WARNINGS" not in "\n".join(captured.messages)

    async def test_a_configured_environment_reports_clean(self, monkeypatch):
        """No false alarms once everything is actually wired up."""
        from app.core.config_simple import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
        monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "coredent-prod-bucket")
        monkeypatch.setattr(settings, "SENTRY_DSN", "https://x@y/1")
        monkeypatch.setattr(settings, "SMTP_USER", "user")
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(settings, "REDIS_URL", "redis://example/0")
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["api.example.com"])
        monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://app.example.com"])
        monkeypatch.setattr(settings, "RECAPTCHA_SECRET_KEY", "secret")
        monkeypatch.setenv("CLAMAV_HOST", "clamav.railway.internal")

        with _CaptureMainLogs() as captured:
            await _run_startup()

        text = "\n".join(captured.messages)
        assert "READINESS WARNINGS" not in text
        assert "all configured integrations present" in text
