"""
Application configuration.

This module reads from environment variables and enforces strict
production-safety checks.  The principle: **fail closed at import time**.
If a required production setting is missing or is a known-bad default, the
process refuses to start rather than running insecurely.
"""

import ipaddress
import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised at import time when a required production setting is missing
    or unsafe."""


# Sentinel dev-defaults that we *must never* see in production.
_BAD_SECRET_PREFIXES = (
    "dev-secret-key",
    "change-me",
    "your-secret",
    "todo",
    "tbd",
)
_BAD_ENCRYPTION_PREFIXES = (
    "dev-encryption-key",
    "change-me",
    "todo",
    "tbd",
)
_KNOWN_PUBLIC_OR_CI_KEYS = (
    "PvnBaoBQL_jDbSXK8XbpML8gEeATsgixL0jOTi6zBY0=",
)

# Placeholder substrings found in the committed .env.production template
# (CHANGE_THIS_*, your-*, yourdomain, ...). A deploy that copies the template
# verbatim must fail closed instead of booting with live-looking placeholders.
_PLACEHOLDER_TOKENS = (
    "change_this",
    "change_me",
    "change-me",
    "changeme",
    "your-",
    "your_",
    "yourdomain",
    "yoursite",
    "your_site",
    "example.com",
    "todo",
    "tbd",
)


def _looks_like_placeholder(value: str) -> bool:
    """True when a value is an obvious template placeholder."""
    v = (value or "").strip().lower()
    if not v:
        return False
    return any(token in v for token in _PLACEHOLDER_TOKENS)


# Environments where the committed dev defaults (SECRET_KEY / ENCRYPTION_KEY),
# console email/SMS, SQLite and DEBUG=True are acceptable for local work.
# EVERYTHING ELSE — "production", "staging", "uat", "preview", or even a
# typo'd "prod" — is treated as a real deployment and must pass the full
# production-safety net below.  This closes the cliff where an environment
# string that was not exactly "production" booted silently on the committed
# dev secret keys.
_LOCAL_ENVIRONMENTS = frozenset(
    {"development", "dev", "test", "testing", "local"}
)


class SimpleSettings:
    def __init__(self):
        # Application
        self.APP_NAME = "CoreDent API"
        self.APP_VERSION = "1.0.0"
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
        # DEBUG defaults to on for local development so the lifespan's
        # ``create_all`` actually builds a fresh database (run_local_dev.sh
        # and plain ``uvicorn`` do not run Alembic migrations). Any non-local
        # environment (production/staging/uat/...) defaults to off — there,
        # Alembic migrations are the only DDL path and DEBUG must never leak.
        self.DEBUG = (
            os.getenv(
                "DEBUG",
                "false" if self.ENVIRONMENT not in _LOCAL_ENVIRONMENTS else "true",
            ).lower()
            == "true"
        )

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./coredent_dev.db"
        )
        self.DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
        self.DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
# Usage metering for usage-based subscription billing. Default OFF is
        # the safe default: metering writes one record per successful
        # authenticated API call, so it is an explicit operator choice to
        # enable (see main.py UsageTrackingMiddleware registration). If the
        # product sells usage-based plans, set USAGE_TRACKING_ENABLED=true in
        # production — otherwise Subscription.current_usage stays 0 and usage
        # invoices bill nothing.
        self.USAGE_TRACKING_ENABLED = (
            os.getenv("USAGE_TRACKING_ENABLED", "false").strip().lower() == "true"
        )

        # Security
        self.SECRET_KEY = os.getenv(
            "SECRET_KEY", "dev-secret-key-change-in-production-for-hipaa-compliance"
        )
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
        )
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )
        # M-4 FIX (safe default): absolute cap on a refresh-token family.
        # expires_at slides on every rotation (idle timeout), so without a
        # cap an active user refreshes forever. created_at + this bound is
        # the hard stop forcing re-authentication (default 30 days).
        self.REFRESH_ABSOLUTE_EXPIRE_DAYS = int(
            os.getenv("REFRESH_ABSOLUTE_EXPIRE_DAYS", "30")
        )
        self.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = int(
            os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS", "24")
        )

        # CORS
        cors_str = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://localhost:8080,http://localhost:8082",
        )
        self.CORS_ORIGINS = [o.strip() for o in cors_str.split(",") if o.strip()]

        # Allowed hosts
        hosts_str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
        self.ALLOWED_HOSTS = [h.strip() for h in hosts_str.split(",") if h.strip()]

        # Rate limiting
        self.RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))

        # Reverse-proxy trust. ``*`` is convenient for local ASGI clients, but
        # production must name the actual load-balancer address/ranges so a
        # caller cannot spoof X-Forwarded-For and evade IP rate limits.
        default_trusted_proxies = "*" if self.ENVIRONMENT in _LOCAL_ENVIRONMENTS else ""
        self.TRUSTED_PROXIES = os.getenv(
            "TRUSTED_PROXIES", default_trusted_proxies
        ).strip()

        # Frontend URL
        self.FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

        # Email
        self.SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM = os.getenv("SMTP_FROM", "noreply@coredent.com")
        self.SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "CoreDent PMS")
        self.EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp" if self.ENVIRONMENT == "production" else "console").strip().lower()
        self.EMAIL_FROM = os.getenv("EMAIL_FROM", self.SMTP_FROM)
        self.EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", self.SMTP_FROM_NAME)
        self.SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

        # SMS / Twilio
        self.SMS_PROVIDER = os.getenv("SMS_PROVIDER", "twilio" if self.ENVIRONMENT == "production" else "console").strip().lower()
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

        # AWS
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
        self.AWS_S3_BUCKET_NAME = (
            os.getenv("AWS_S3_BUCKET_NAME", "") or self.AWS_S3_BUCKET
        )
        self.AWS_CLOUDFRONT_DOMAIN = os.getenv("AWS_CLOUDFRONT_DOMAIN", "")
        self.AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

        # Encryption (single key, retained for backward compat; keyring prefers
        # ENCRYPTION_KEYS for rotation).
        self.ENCRYPTION_KEY = os.getenv(
            "ENCRYPTION_KEY", "dev-encryption-key-change-in-production"
        )
        self.ENCRYPTION_KEYS = os.getenv("ENCRYPTION_KEYS", "")
        self.SEARCH_INDEX_KEY = os.getenv("SEARCH_INDEX_KEY", "")

        # KMS backend selection (app/core/kms.py). 'env' | 'aws' | 'local'.
        self.KMS_BACKEND = (os.getenv("KMS_BACKEND", "env") or "env").strip().lower()
        self.AWS_KMS_KEY_ARN = os.getenv("AWS_KMS_KEY_ARN", "").strip()

        # Redis
        self.REDIS_URL = os.getenv("REDIS_URL", "")
        self.REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "3600"))

        # Sentry
        self.SENTRY_DSN = os.getenv("SENTRY_DSN", "")

        # Stripe
        self.STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
        self.STRIPE_SECRET_KEY = (
            os.getenv("STRIPE_SECRET_KEY", "") or self.STRIPE_API_KEY
        )
        self.STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.STRIPE_WEBHOOK_IP_WHITELIST_ENABLED = (
            os.getenv("STRIPE_WEBHOOK_IP_WHITELIST_ENABLED", "true").lower() == "true"
        )
        self.STRIPE_WEBHOOK_HMAC_SECRET = os.getenv("STRIPE_WEBHOOK_HMAC_SECRET", "")

        # CAPTCHA
        self.RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
        self.RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
        self.HCAPTCHA_SECRET_KEY = os.getenv("HCAPTCHA_SECRET_KEY", "")
        self.HCAPTCHA_SITE_KEY = os.getenv("HCAPTCHA_SITE_KEY", "")

        # Celery
        self.CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "") or self.REDIS_URL
        self.CELERY_RESULT_BACKEND = (
            os.getenv("CELERY_RESULT_BACKEND", "") or self.REDIS_URL
        )

        # Razorpay
        self.RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
        self.RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

        # Insurance EDI
        self.DXC_API_KEY = os.getenv("DXC_API_KEY", "")
        self.DXC_API_SECRET = os.getenv("DXC_API_SECRET", "")
        self.DXC_BASE_URL = os.getenv(
            "DXC_BASE_URL", "https://api.dentalxchange.com/v2"
        )

        # QuickBooks
        self.QB_CLIENT_ID = os.getenv("QB_CLIENT_ID", "")
        self.QB_CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET", "")
        self.QB_REDIRECT_URI = os.getenv("QB_REDIRECT_URI", "")
        self.QB_ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "sandbox")

        # File upload
        self.MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))
        ext_str = os.getenv("ALLOWED_EXTENSIONS", "pdf,jpg,jpeg,png,doc,docx")
        self.ALLOWED_EXTENSIONS = [e.strip() for e in ext_str.split(",") if e.strip()]

        # Pagination
        self.DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "10"))
        self.MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))

        # Subscription access policy. Past-due accounts retain access during
        # this explicit grace period so a transient payment failure does not
        # interrupt clinical operations; expired/unpaid accounts are blocked.
        self.SUBSCRIPTION_PAST_DUE_GRACE_DAYS = int(
            os.getenv("SUBSCRIPTION_PAST_DUE_GRACE_DAYS", "7")
        )

        # HIPAA Compliance
        self.AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
        # M-4 PRODUCT DECISION (explicit): SESSION_TIMEOUT_MINUTES is a legacy
        # alias — the authoritative idle control is ACCESS_TOKEN_EXPIRE_MINUTES
        # (15m) for access tokens plus REFRESH_TOKEN_EXPIRE_DAYS (7d sliding)
        # for refresh. Kept for .env compat; not separately enforced.
        self.SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "15"))
        self.PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
        self.PASSWORD_REQUIRE_UPPERCASE = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
        self.PASSWORD_REQUIRE_LOWERCASE = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
        self.PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
        self.PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
        # Data-retention policy enforcement (docs/DATA_RETENTION_POLICY.md § R1-R2).
        # Anonymized patient rows + orphaned billing history are eligible for the
        # scheduled hard purge once the last billing disposition is older than
        # RETENTION_ANONYMIZED_PURGE_YEARS. The purge task diagnoses eligibility
        # with a UTC comparison; this setting is the default retention window.
        self.RETENTION_ANONYMIZED_PURGE_YEARS = int(os.getenv("RETENTION_ANONYMIZED_PURGE_YEARS", "7"))
        self.RETENTION_ANONYMIZED_PURGE_BATCH_SIZE = int(os.getenv("RETENTION_ANONYMIZED_PURGE_BATCH_SIZE", "50"))
        self.RETENTION_ANONYMIZED_PURGE_ENABLED = os.getenv("RETENTION_ANONYMIZED_PURGE_ENABLED", "true").lower() == "true"
        # M-4 PRODUCT DECISION (explicit): PASSWORD_EXPIRE_DAYS is
        # intentionally NOT enforced. NIST SP 800-63B §5.1.1.2 deprecates
        # periodic rotation (it drives weaker passwords); rotation is enforced
        # on compromise (password_changed_at invalidates sessions) instead.
        # Kept for .env compat so old deploys do not crash on unknown vars.
        self.PASSWORD_EXPIRE_DAYS = int(os.getenv("PASSWORD_EXPIRE_DAYS", "90"))

        # Monitoring
        self.MONITORING_TOKEN = os.getenv("MONITORING_TOKEN", "").strip()

        # Sentry DSN placeholder rejection
        if self.SENTRY_DSN and (
            "your-sentry-dsn" in self.SENTRY_DSN
            or self.SENTRY_DSN.strip().lower() in {"changeme", "todo", "tbd"}
        ):
            self.SENTRY_DSN = ""

        # Production safety net.  Every one of these would let the system run
        # but cause silent failures; we fail boot loudly instead.  It applies
        # to ANY non-local environment (see _LOCAL_ENVIRONMENTS) so a
        # staging/preview/UAT deploy can never silently run on the committed
        # dev secret keys.
        if self.ENVIRONMENT not in _LOCAL_ENVIRONMENTS:
            errors = []
            # M-6 FIX: fail closed if a real deployment points at SQLite.
            # FOR UPDATE / pg_advisory locks degrade to check-then-insert on
            # SQLite, silently losing double-payment/double-booking guards.
            _db_url = (self.DATABASE_URL or "").lower()
            if _db_url.startswith("sqlite"):
                errors.append(
                    "DATABASE_URL uses SQLite, which does not enforce row-level "
                    "or advisory locks. Production/staging deployments must use "
                    "PostgreSQL."
                )
            if (
                not os.getenv("SECRET_KEY")
                or self.SECRET_KEY.startswith(_BAD_SECRET_PREFIXES)
                or _looks_like_placeholder(self.SECRET_KEY)
            ):
                errors.append(
                    "SECRET_KEY is missing or uses a known-bad default "
                    "(must be set to a strong, unique production value)."
                )
            elif len(self.SECRET_KEY) < 32:
                errors.append("SECRET_KEY must be at least 32 characters.")

            # Encryption keys
            multi = self.ENCRYPTION_KEYS.strip()
            legacy = (self.ENCRYPTION_KEY or "").strip()
            if (
                (not multi and (not legacy or legacy.startswith(_BAD_ENCRYPTION_PREFIXES)))
                or _looks_like_placeholder(legacy)
                or _looks_like_placeholder(multi)
                or any(k in multi or k in legacy for k in _KNOWN_PUBLIC_OR_CI_KEYS)
            ):
                errors.append(
                    "ENCRYPTION_KEYS (or legacy ENCRYPTION_KEY) is required in "
                    "production and must not be a template placeholder or known public/CI key. "
                    'Generate one with: python -c "from app.core.encryption '
                    'import generate_key; print(generate_key())"'
                )

            # Search indexes are HMACs over sensitive normalized values. They
            # must use an independent secret: deriving from a public Fernet
            # key ID makes every stored index predictable to a database thief.
            search_index_key = self.SEARCH_INDEX_KEY.strip()
            if (
                not search_index_key
                or _looks_like_placeholder(search_index_key)
                or len(search_index_key) < 32
            ):
                errors.append(
                    "SEARCH_INDEX_KEY is required outside local environments and "
                    "must be an independent, non-placeholder secret of at least "
                    "32 characters; it must not be derived from a public encryption "
                    "key ID."
                )

            # KMS misconfiguration used to surface only at the first encrypt/
            # decrypt call. Fail at boot instead so a bad deploy never serves
            # traffic that cannot read or write PHI.
            if self.KMS_BACKEND not in ("env", "aws", "local"):
                errors.append(
                    f"KMS_BACKEND={self.KMS_BACKEND!r} is not valid; use one of "
                    "'env', 'aws', or 'local'."
                )
            elif self.KMS_BACKEND == "aws":
                if not self.AWS_KMS_KEY_ARN:
                    errors.append(
                        "KMS_BACKEND=aws requires AWS_KMS_KEY_ARN to be set."
                    )
                if not any(
                    entry.strip().startswith("aws:")
                    for entry in self.ENCRYPTION_KEYS.split(",")
                ):
                    errors.append(
                        "KMS_BACKEND=aws requires an 'aws:<encrypted-data-key>' "
                        "entry in ENCRYPTION_KEYS (see "
                        "scripts/generate_aws_data_key.py)."
                    )

            if not self.SENTRY_DSN:
                errors.append(
                    "SENTRY_DSN is required in production. Set the DSN from "
                    "your Sentry project dashboard; otherwise you will have "
                    "NO visibility into production errors."
                )

            if not self.STRIPE_WEBHOOK_SECRET or _looks_like_placeholder(self.STRIPE_WEBHOOK_SECRET):
                errors.append(
                    "STRIPE_WEBHOOK_SECRET is required in production. Stripe "
                    "webhooks will not be verified and the app will refuse to "
                    "process payment events until this is set."
                )

            if not self.REDIS_URL:
                errors.append(
                    "REDIS_URL is required in production. The in-process "
                    "rate limiter does not work across multiple workers and "
                    "is unsafe for a multi-replica deployment."
                )

            # Uvicorn and application-level rate limiting must agree about
            # which proxy hops are trusted. Reject wildcards, empty values,
            # and malformed addresses before the process can accept traffic.
            if not self.TRUSTED_PROXIES or self.TRUSTED_PROXIES == "*":
                errors.append(
                    "TRUSTED_PROXIES is required in production and must list "
                    "explicit proxy IPs or CIDR ranges; '*' is not allowed."
                )
            else:
                invalid_proxies = []
                for proxy in self.TRUSTED_PROXIES.split(","):
                    proxy = proxy.strip()
                    if not proxy:
                        invalid_proxies.append("<empty>")
                        continue
                    try:
                        ipaddress.ip_network(proxy, strict=False)
                    except ValueError:
                        invalid_proxies.append(proxy)
                if invalid_proxies:
                    errors.append(
                        "TRUSTED_PROXIES contains invalid IP/CIDR entries: "
                        + ", ".join(invalid_proxies)
                    )

            if (
                not self.MONITORING_TOKEN
                or _looks_like_placeholder(self.MONITORING_TOKEN)
                or len(self.MONITORING_TOKEN) < 32
            ):
                errors.append(
                    "MONITORING_TOKEN is required in production, must not be a "
                    "template placeholder, and must be at least 32 characters."
                )

            if (
                not self.SMTP_USER
                or _looks_like_placeholder(self.SMTP_USER)
                or self.SMTP_HOST == "localhost"
                or _looks_like_placeholder(self.SMTP_HOST)
                or _looks_like_placeholder(self.SMTP_PASSWORD)
            ):
                errors.append(
                    "SMTP is not configured. Password resets, email "
                    "verification, and appointment reminders will fail. "
                    "Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD before "
                    "going to production."
                )

            if not self.AWS_S3_BUCKET or _looks_like_placeholder(self.AWS_S3_BUCKET):
                errors.append(
                    "AWS_S3_BUCKET is not set. File and image uploads will "
                    "fail. Configure an S3 bucket (or compatible store) "
                    "before going to production."
                )

            if (
                not self.ALLOWED_HOSTS
                or self.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
                or any(_looks_like_placeholder(h) for h in self.ALLOWED_HOSTS)
            ):
                errors.append(
                    "ALLOWED_HOSTS is set to development defaults or template "
                    "placeholders. Configure your production domain(s) to "
                    "protect against Host header attacks."
                )

            if self.CORS_ORIGINS and (
                any("localhost" in o for o in self.CORS_ORIGINS)
                or any(_looks_like_placeholder(o) for o in self.CORS_ORIGINS)
                or "*" in self.CORS_ORIGINS
            ):
                errors.append(
                    "CORS_ORIGINS contains a localhost origin, template "
                    "placeholder, or wildcard '*'. Configure explicit "
                    "production origins before going to production."
                )

            if errors:
                raise ConfigError(
                    f"Refusing to start: environment '{self.ENVIRONMENT}' is not a "
                    "local/dev environment and requires production-grade configuration "
                    "(local/dev/test environments are exempt):\n  - "
                    + "\n  - ".join(errors)
                    + "\nSee docs/PRODUCTION_REQUIRED_ENV.md for the full list."
                )


settings = SimpleSettings()
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS
