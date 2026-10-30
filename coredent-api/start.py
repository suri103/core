#!/usr/bin/env python3
"""CoreDent process entrypoint (web / worker / beat / release).

One image, several roles.  ``PROCESS_TYPE`` selects which:

    web      uvicorn API server (default)
    worker   Celery worker consuming default,communications,reminders,emails
    beat     Celery beat scheduler
    release  run migrations only, then exit (for a platform release phase)

Railway/Vercel have no Heroku-style release phase, so the API role also runs
``alembic upgrade head`` at boot.  That used to be unsafe: a rolling deploy
starts several replicas at once and they would race each other's DDL.  It is
now serialised with a PostgreSQL *session-level advisory lock*, so exactly one
replica migrates and the others block, then observe an already-current schema
and continue.  See ``run_migrations``.

SECURITY: Uvicorn is started with ``proxy_headers=True`` so that
``request.client.host`` and audit-log IP columns reflect the real client IP
(from ``X-Forwarded-For``) rather than the load balancer's internal IP.
Without this, behind Railway/Vercel/etc, every audit row would record the LB's
IP, making the HIPAA audit log operationally useless and breaking per-IP rate
limiting.

The ``forwarded_allow_ips`` setting trusts the proxy chain only on the
configured addresses. In production set ``TRUSTED_PROXIES`` to the platform
edge range to avoid spoofing via a client-set ``X-Forwarded-For`` header.
"""

import faulthandler
import logging
import os
import sys

# Dump a native traceback on SIGSEGV/SIGABRT/SIGBUS/SIGFPE/SIGILL.
#
# A migration step kills this process with no Python traceback and no log line
# at all, which means it is dying natively rather than raising: run_migrations()
# already logs and re-raises every Python exception, and none appears. This
# makes a native crash print its stack to stderr instead of exiting silently.
#
# If a deploy shows no output from this either, the process is being killed
# from outside (a memory-cgroup OOM kill cannot be caught), which points at the
# container's memory limit rather than at the migration itself.
faulthandler.enable()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Arbitrary but fixed: every replica must derive the same advisory-lock key.
_MIGRATION_LOCK_KEY = 0x0C0DE_DEA7
# How long a replica waits for a peer to finish migrating before giving up.
_MIGRATION_LOCK_TIMEOUT_SECONDS = 300

CELERY_APP = "app.core.celery_app:celery_app"
CELERY_QUEUES = "default,communications,reminders,emails"

# Environments where a failed migration is tolerated (local iteration only).
# Anything else — production, staging, uat, preview — must refuse to start:
# booting with a half-applied schema serves 500s on every DB-backed route
# while /health still reports healthy, which is far worse than a failed deploy.
_LENIENT_MIGRATION_ENVIRONMENTS = frozenset(
    {"development", "dev", "test", "testing", "local"}
)


def _normalise_db_url(database_url: str) -> str:
    """Railway hands out ``postgres://``; SQLAlchemy/Alembic need ``postgresql://``."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def _current_revision(database_url: str) -> str:
    """Best-effort current Alembic revision. Diagnostics only, never raises."""
    try:
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine

        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                return MigrationContext.configure(conn).get_current_revision() or "<none>"
        finally:
            engine.dispose()
    except Exception as exc:  # noqa: BLE001 - diagnostics must not mask the real error
        return f"<unavailable: {exc}>"


def _alembic_upgrade(database_url: str) -> None:
    import alembic.command
    import alembic.config

    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    # Revisions commit individually (see alembic/env.py), so on a retry this
    # names the revision the previous attempt stopped at - i.e. the culprit.
    logger.info("Current revision before upgrade: %s", _current_revision(database_url))
    logger.info("Executing: alembic upgrade head")
    alembic.command.upgrade(alembic_cfg, "head")


def _upgrade_under_advisory_lock(database_url: str) -> None:
    """Serialise ``alembic upgrade head`` across concurrently booting replicas.

    A session-level ``pg_advisory_lock`` is held on a dedicated connection for
    the duration of the migration run.  Alembic opens its own connection, so
    the lock acts purely as a cross-process mutex.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            # Bound the wait so a wedged peer cannot hang the deploy forever.
            conn.execute(
                text(f"SET lock_timeout = '{_MIGRATION_LOCK_TIMEOUT_SECONDS}s'")
            )
            conn.commit()
            logger.info("Acquiring migration advisory lock...")
            try:
                conn.execute(
                    text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY}
                )
                conn.commit()
            except Exception as exc:  # lock_timeout or connection issue
                raise RuntimeError(
                    "Timed out waiting for the migration advisory lock; another "
                    "replica may be mid-migration or wedged."
                ) from exc

            logger.info("Migration advisory lock acquired.")
            try:
                _alembic_upgrade(database_url)
            finally:
                try:
                    conn.execute(
                        text("SELECT pg_advisory_unlock(:k)"),
                        {"k": _MIGRATION_LOCK_KEY},
                    )
                    conn.commit()
                    logger.info("Migration advisory lock released.")
                except Exception:
                    # Session-level locks are released when the connection
                    # closes, so this is best-effort only.
                    logger.warning("Advisory unlock failed; lock frees on disconnect.")
    finally:
        engine.dispose()


def run_migrations() -> bool:
    """Run database migrations using Alembic.

    In production, migration failure is fatal — we refuse to start with an
    out-of-sync schema. In development we log and continue so contributors
    aren't blocked by transient issues.
    """
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    try:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.warning("DATABASE_URL not set - skipping migrations")
            return True

        database_url = _normalise_db_url(database_url)

        logger.info("=" * 60)
        logger.info("STARTING DATABASE MIGRATIONS")
        logger.info("=" * 60)
        logger.info(f"Database URL: {database_url.split('@')[0]}@***")

        if database_url.startswith("postgresql"):
            _upgrade_under_advisory_lock(database_url)
        else:
            # SQLite (dev/test) is single-writer; no cross-replica race exists.
            _alembic_upgrade(database_url)

        logger.info("=" * 60)
        logger.info("DATABASE MIGRATIONS COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        return True
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"MIGRATION FAILED: {e}")
        logger.error("=" * 60)
        import traceback

        logger.error(traceback.format_exc())
        # Revisions commit individually, so the revision reached here is exactly
        # the one that failed - the actionable line in a crash-looping deploy.
        try:
            logger.error("Revision reached before failure: %s", _current_revision(database_url))
        except Exception:  # noqa: BLE001 - never mask the original failure
            pass

        if environment not in _LENIENT_MIGRATION_ENVIRONMENTS:
            logger.critical(
                "Refusing to start in %r with failed migrations. "
                "Fix the migration and redeploy.",
                environment,
            )
            sys.exit(1)

        logger.warning("Continuing with server startup despite migration warning...")
        return False


def _maybe_migrate() -> None:
    """Run migrations unless explicitly disabled.

    Set ``RUN_MIGRATIONS_ON_START=false`` when you drive migrations from a
    dedicated ``PROCESS_TYPE=release`` job instead.
    """
    run_on_start = os.environ.get("RUN_MIGRATIONS_ON_START", "true").strip().lower()
    if run_on_start in {"1", "true", "yes"}:
        run_migrations()
    else:
        logger.info("RUN_MIGRATIONS_ON_START is disabled; skipping migrations.")


def start_web() -> None:
    import uvicorn
    from app.core.config_simple import settings

    # Read the validated settings object rather than independently applying
    # environment defaults here. Uvicorn's proxy trust and the application's
    # client-IP/rate-limit resolver must use the exact same allowlist.
    environment = settings.ENVIRONMENT
    _maybe_migrate()

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    trusted_proxies = settings.TRUSTED_PROXIES

    logger.info(f"Starting CoreDent API on {host}:{port} (env={environment})")
    logger.info(f"Trusted proxies for X-Forwarded-For: {trusted_proxies}")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips=trusted_proxies,
    )


def _exec_celery(args: list[str]) -> None:
    """Replace this process with Celery so signals/exit codes pass through."""
    from celery.__main__ import main as celery_main

    logger.info("Exec: celery %s", " ".join(args))
    sys.argv = ["celery", *args]
    raise SystemExit(celery_main())


def start_worker() -> None:
    # Workers must never migrate: DDL belongs to the web/release role only.
    concurrency = os.environ.get("CELERY_CONCURRENCY", "4")
    queues = os.environ.get("CELERY_QUEUES", CELERY_QUEUES)
    _exec_celery(
        [
            "-A",
            CELERY_APP,
            "worker",
            "-Q",
            queues,
            "--concurrency",
            concurrency,
            "-l",
            os.environ.get("CELERY_LOG_LEVEL", "info"),
        ]
    )


def start_beat() -> None:
    _exec_celery(
        [
            "-A",
            CELERY_APP,
            "beat",
            "-l",
            os.environ.get("CELERY_LOG_LEVEL", "info"),
        ]
    )


def start_release() -> None:
    """One-shot migration job for platforms with a real release phase."""
    ok = run_migrations()
    raise SystemExit(0 if ok else 1)


_ROLES = {
    "web": start_web,
    "api": start_web,
    "worker": start_worker,
    "beat": start_beat,
    "scheduler": start_beat,
    "release": start_release,
    "migrate": start_release,
}


def main() -> None:
    process_type = os.environ.get("PROCESS_TYPE", "web").strip().lower()
    role = _ROLES.get(process_type)
    if role is None:
        logger.error(
            "Unknown PROCESS_TYPE=%r. Valid values: %s",
            process_type,
            ", ".join(sorted(_ROLES)),
        )
        sys.exit(2)
    logger.info("Starting process role: %s", process_type)
    role()


if __name__ == "__main__":
    main()
