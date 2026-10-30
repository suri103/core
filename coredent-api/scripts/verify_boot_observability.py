"""Phase 3 boot & observability verification (run manually, not part of CI).

1. Fail-closed boot: production-like env without required secrets must abort.
2. Valid production-like env must boot; /health must report DB status;
   /metrics must be protected; security headers present on responses.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILURES = []


def expect_boot_failure(env_overrides, label):
    """Run boot in a subprocess with the given env; expect non-zero exit."""
    import subprocess

    full_env = {**os.environ, **env_overrides}
    code = (
        "import app.main"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=full_env,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
        timeout=120,
    )
    if result.returncode == 0:
        FAILURES.append(f"{label}: booted successfully but should have failed closed")
        print(f"FAIL {label}")
    else:
        tail = (result.stderr or "").strip().splitlines()
        reason = next(
            (line for line in reversed(tail) if "SECRET" in line or "ENCRYPTION" in line or "REDIS" in line or "SENTRY" in line or "STRIPE" in line or "CORS" in line or "HOST" in line),
            tail[-1] if tail else "?",
        )
        print(f"OK   {label} -> aborted with: {reason[:120]}")


def check_live_app():
    """Boot with valid prod-like env and probe endpoints via httpx ASGI."""
    os.environ.update(
        {
            "ENVIRONMENT": "production",
            "DEBUG": "False",
            "SECRET_KEY": "x" * 64,
            "ENCRYPTION_KEY": "ojgJ3oQf7At2eiaGVqzSAitO_8dokW47KIPT_0NB8-g=",
            "REDIS_URL": "redis://localhost:6379/0",
            "SENTRY_DSN": "https://examplekey@o123.ingest.de.sentry.io/456",
            "STRIPE_SECRET_KEY": "sk_test_dummy",
            "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
            "SMTP_HOST": "smtp.postmark-coredent.io",
            "SMTP_USER": "noreply@coredent-prod.io",
            "SMTP_PASSWORD": "smtp-password-1234",
            "AWS_S3_BUCKET": "coredent-prod-uploads",
            "CORS_ORIGINS": "https://app.coredent-prod.io",
            "ALLOWED_HOSTS": "api.coredent-prod.io",
            "SEARCH_INDEX_KEY": "s" * 32,
            "TRUSTED_PROXIES": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
            "MONITORING_TOKEN": "m" * 32,
            "DATABASE_URL": f"sqlite+aiosqlite:///{Path('.boot-check.sqlite').as_posix()}",
        }
    )
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app, client=("10.0.0.1", 1000))
    with httpx.Client(transport=transport, base_url="https://api.coredent-prod.io") as client:
        r = client.get("/health")
        body = r.json()
        print(f"/health -> {r.status_code} db={body.get('database') or body.get('status')}")
        if r.status_code != 200:
            FAILURES.append("/health did not return 200")

        r = client.get("/health")
        server_hdr = r.headers.get("server", "")
        csp = r.headers.get("content-security-policy", "")
        xfo = r.headers.get("x-frame-options", "")
        print(f"security headers: server={server_hdr!r} csp={'yes' if csp else 'NO'} xfo={'yes' if xfo else 'NO'}")
        if not csp or not xfo:
            FAILURES.append("security headers missing")

        r = client.get("/metrics")
        print(f"/metrics unauthenticated -> {r.status_code} (expect 401 or 403)")
        if r.status_code not in (401, 403):
            FAILURES.append("/metrics is not protected")


if __name__ == "__main__":
    # 1. Missing SECRET_KEY in production must abort.
    env = {
        "ENVIRONMENT": "production",
        "DEBUG": "False",
        "SECRET_KEY": "",
        "ENCRYPTION_KEY": "ojgJ3oQf7At2eiaGVqzSAitO_8dokW47KIPT_0NB8-g=",
        "REDIS_URL": "redis://localhost:6379/0",
        "SENTRY_DSN": "https://k@o1.ingest.de.sentry.io/2",
        "STRIPE_WEBHOOK_SECRET": "whsec_x",
        "SMTP_HOST": "smtp.postmark-coredent.io",
        "SMTP_USER": "noreply@coredent-prod.io",
        "SMTP_PASSWORD": "smtp-password-1234",
        "AWS_S3_BUCKET": "coredent-prod-uploads",
        "CORS_ORIGINS": "https://app.coredent-prod.io",
        "ALLOWED_HOSTS": "api.coredent-prod.io",
    }
    print("== step 1: prod boot without SECRET_KEY ==")
    expect_boot_failure(env, "prod boot without SECRET_KEY")

    # 2. Wildcard CORS in production must abort.
    env_wc = {**env, "SECRET_KEY": "y" * 64, "CORS_ORIGINS": "*"}
    print("== step 2: prod boot with wildcard CORS ==")
    expect_boot_failure(env_wc, "prod boot with wildcard CORS")

    # 3. Live probes with a fully valid production-like configuration.
    print("== step 3: live probes ==")
    check_live_app()

    Path(".boot-check.sqlite").unlink(missing_ok=True)

    if FAILURES:
        print("\nBOOT/OBSERVABILITY CHECK FAILED:")
        for f in FAILURES:
            print(f" - {f}")
        sys.exit(1)
    print("\nBOOT/OBSERVABILITY CHECK PASSED")
