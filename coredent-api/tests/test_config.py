"""Tests for configuration validation"""
import os

import pytest
from cryptography.fernet import Fernet


class TestSimpleSettings:
    def test_access_token_default_15(self):
        from app.core.config_simple import SimpleSettings
        old = os.environ.pop("ACCESS_TOKEN_EXPIRE_MINUTES", None)
        try:
            s = SimpleSettings()
            assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
        finally:
            if old:
                os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = old

    def test_environment_default_dev(self):
        from app.core.config_simple import SimpleSettings
        old = os.environ.pop("ENVIRONMENT", None)
        try:
            s = SimpleSettings()
            assert s.ENVIRONMENT == "development"
        finally:
            if old:
                os.environ["ENVIRONMENT"] = old

    def test_cors_parsing(self):
        from app.core.config_simple import SimpleSettings
        os.environ["CORS_ORIGINS"] = "http://a.com,http://b.com"
        try:
            s = SimpleSettings()
            assert "http://a.com" in s.CORS_ORIGINS
            assert "http://b.com" in s.CORS_ORIGINS
        finally:
            del os.environ["CORS_ORIGINS"]

    def test_env_override(self):
        """APP_NAME is a constant (not env-driven); confirm it is stable."""
        from app.core.config_simple import SimpleSettings

        s = SimpleSettings()
        assert s.APP_NAME == "CoreDent API"

    def test_database_url_default(self):
        from app.core.config_simple import SimpleSettings
        old = os.environ.pop("DATABASE_URL", None)
        try:
            s = SimpleSettings()
            assert "coredent_dev.db" in s.DATABASE_URL
        finally:
            if old:
                os.environ["DATABASE_URL"] = old


class TestProductionConfig:
    """Verify production configuration behavior."""

    def _prod_env(self, debug: str):
        os.environ["ENVIRONMENT"] = "production"
        # M-6 FIX: production must use PostgreSQL (SQLite loses row-level and
        # advisory locks). Tests that boot production config must name Postgres.
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost:5432/coredent"
        os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        os.environ["SECRET_KEY"] = "x" * 32
        os.environ["SEARCH_INDEX_KEY"] = "x" * 32
        os.environ["DEBUG"] = debug
        os.environ["SENTRY_DSN"] = "https://x@sentry.io/1"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_x"
        os.environ["REDIS_URL"] = "redis://x"
        os.environ["TRUSTED_PROXIES"] = "127.0.0.1"
        os.environ["MONITORING_TOKEN"] = "m" * 32
        os.environ["SMTP_HOST"] = "x"
        os.environ["SMTP_USER"] = "x"
        os.environ["SMTP_PASSWORD"] = "x"
        os.environ["AWS_S3_BUCKET"] = "x"
        os.environ["ALLOWED_HOSTS"] = "api.acmepractice.com"
        os.environ["CORS_ORIGINS"] = "https://app.acmepractice.com"

    def _clean_prod_env(self):
        os.environ["ENVIRONMENT"] = "development"
        for k in (
            "DATABASE_URL",
            "ENCRYPTION_KEY",
            "SECRET_KEY",
            "SEARCH_INDEX_KEY",
            "DEBUG",
            "TRUSTED_PROXIES",
            "MONITORING_TOKEN",
        ):
            os.environ.pop(k, None)

    def test_production_environment_sets_correctly(self):
        self._prod_env("false")
        try:
            from app.core.config_simple import SimpleSettings
            s = SimpleSettings()
            assert s.ENVIRONMENT == "production"
            assert s.DEBUG is False
        finally:
            self._clean_prod_env()

    def test_sqlite_refused_in_production(self):
        """M-6 regression: SQLite in production must fail closed."""
        from app.core.config_simple import ConfigError, SimpleSettings

        self._prod_env("false")
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./oops.db"
        try:
            with __import__("pytest").raises(ConfigError, match="PostgreSQL"):
                SimpleSettings()
        finally:
            self._clean_prod_env()

    def test_debug_true_in_production(self):
        """DEBUG=True in production is allowed by config (should be caught by deployment checks)."""
        self._prod_env("true")
        try:
            from app.core.config_simple import SimpleSettings
            s = SimpleSettings()
            assert s.DEBUG is True
            assert s.ENVIRONMENT == "production"
        finally:
            self._clean_prod_env()
