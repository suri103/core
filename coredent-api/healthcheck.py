#!/usr/bin/env python3
"""Process-type-aware container healthcheck.

``Dockerfile HEALTHCHECK`` runs in *every* role of the shared image, but only
the web role serves HTTP. Curling ``/health`` from a worker/beat container
would fail forever and restart-loop Celery. This script selects the probe to
match ``PROCESS_TYPE``:

    web       HTTP GET /health must return 2xx
    worker    broker reachable AND ≥1 task registered on the worker app
    beat      broker reachable (beat only publishes schedules)
    release   transient one-shot job: always healthy
    (unset)   treated as web — mirrors the CMD default
"""

import os
import sys
import urllib.request

# Should echo the CMD/web default in start.py ("web").
PROCESS_TYPE = os.environ.get("PROCESS_TYPE", "web").strip().lower()
# Must mirror the CMD/web default in start.py. The Dockerfile explicitly sets
# PORT=3000 for HTTP, so only an unset variable falls back to 8000.
HEALTH_PORT = int(os.environ.get("PORT", 8000))
HEALTH_TIMEOUT_SECONDS = 5


def _broker_url() -> str:
    url = (
        os.environ.get("CELERY_BROKER_URL")
        or os.environ.get("REDIS_URL")
        or "redis://localhost:6379/0"
    )
    # The Redis client wants redis:// even though platforms hand out rediss://
    # with TLS credentials; keep whatever scheme was provided.
    if url.startswith("postgres://"):
        # Mis-configured broker becomes a hard failure instead of a confusing 0
        raise ValueError("CELERY_BROKER_URL is set to a Postgres URL")
    return url


def _check_web() -> bool:
    url = f"http://127.0.0.1:{HEALTH_PORT}/health"
    try:
        with urllib.request.urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _check_broker() -> bool:
    """Broker must accept a connection (Redis PING)."""
    from redis import Redis

    try:
        client = Redis.from_url(
            _broker_url(),
            socket_connect_timeout=HEALTH_TIMEOUT_SECONDS,
            socket_timeout=HEALTH_TIMEOUT_SECONDS,
        )
        return bool(client.ping())
    except Exception:
        return False


def _check_worker() -> bool:
    """Liveness for a worker: broker reachable + app loaded with tasks.

    Deliberately avoids hammering a remote control channel on every probe
    (Chatter + rate limits under heavy load). ``celery_app.tasks`` includes the
    built-ins, so require a minimum task count which only a loading of the
    ``app.core.tasks``/``include`` modules reaches.
    """
    if not _check_broker():
        return False
    try:
        from app.core.celery_app import celery_app

        # Drop built-ins (celery.* + built-in chord/chain etc.) before counting
        registered = {
            name for name in celery_app.tasks if not name.startswith("celery.")
        }
        if not registered:
            return False
    except Exception:
        return False
    return True


def main() -> int:
    if PROCESS_TYPE in {"web", "api"}:
        ok = _check_web()
    elif PROCESS_TYPE in {"worker"}:
        ok = _check_worker()
    elif PROCESS_TYPE in {"beat", "scheduler"}:
        ok = _check_broker()
    elif PROCESS_TYPE in {"release", "migrate"}:
        ok = True
    else:
        print(f"unknown PROCESS_TYPE={PROCESS_TYPE!r}", file=sys.stderr)
        ok = _check_web()

    if not ok:
        print(f"healthcheck failed for PROCESS_TYPE={PROCESS_TYPE}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
