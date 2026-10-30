"""
Database Configuration
SQLAlchemy 2.0 async setup with PostgreSQL
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config_simple import settings

engine_url = settings.DATABASE_URL or ""
# CRIT-01 FIX: Railway uses postgres://, SQLAlchemy async requires postgresql+asyncpg://
if engine_url.startswith("postgres://"):
    engine_url = engine_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif engine_url.startswith("postgresql://"):
    engine_url = engine_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine_kwargs = {
    "echo": settings.DEBUG,
}

# PostgreSQL pool settings.
# NOTE: pool_size/max_overflow are QueuePool options. NullPool (used for
# DEBUG/local so every request gets a fresh connection) rejects them and
# raises TypeError at import time, so the two are mutually exclusive.
if engine_url.startswith("postgresql+"):
    if settings.DEBUG:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs.update(
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
        )

engine = create_async_engine(
    engine_url,
    **engine_kwargs,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Sync engine/session for Celery tasks and other synchronous contexts
# (Celery workers cannot use the async engine directly).
sync_engine_url = engine_url
if sync_engine_url.startswith("postgresql+asyncpg://"):
    sync_engine_url = sync_engine_url.replace("postgresql+asyncpg://", "postgresql://", 1)
elif sync_engine_url.startswith("sqlite+aiosqlite://"):
    sync_engine_url = sync_engine_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

sync_engine = create_engine(
    sync_engine_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency to get database session
    Usage: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # Only commit if no exceptions occurred
            # Let the endpoint decide when to commit
        except Exception:
            await session.rollback()
            raise

# H4 residual hardening: concurrency guards (SELECT ... FOR UPDATE,
# pg_advisory_xact_lock) are real only on PostgreSQL. On SQLite — the local
# dev/test database — both are silently ignored, so guarded sections degrade
# to check-then-insert. That is acceptable for a single-user dev database,
# but it must never happen silently: lock-taking call sites gate through
# row_locks_supported(), which emits one loud warning per process so a
# misconfigured DATABASE_URL (e.g. a deploy accidentally pointed at SQLite)
# is visible in the logs immediately.

_row_locks_warning_emitted = False


def row_locks_supported() -> bool:
    """True when the configured database honors row/advisory locks.

    Returns False on SQLite (and any non-Postgres backend), warning once per
    process so the silent loss of every FOR UPDATE / advisory-lock guard is
    called out in logs instead of being invisible.
    """
    global _row_locks_warning_emitted
    if engine_url.startswith("postgresql"):
        return True
    if not _row_locks_warning_emitted:
        _row_locks_warning_emitted = True
        logging.getLogger(__name__).warning(
            "DATABASE_URL is not PostgreSQL (%r): FOR UPDATE row locks and "
            "advisory locks are NOT enforced, so billing/booking concurrency "
            "guards degrade to check-then-insert. Never use this database "
            "for multi-user or production data.",
            engine_url,
        )
    return False

