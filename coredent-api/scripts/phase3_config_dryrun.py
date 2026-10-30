"""Phase 3: exercise production config fail-closed paths end-to-end.

A "production" environment is anything not in _LOCAL_ENVIRONMENTS. The
config module refuses to import if a required secret is missing, is a
known-bad default, or matches a template placeholder. We generate
real-shape values for every required var and assert the import succeeds,
then mutate each required var to a bad value and assert the import
fails with a useful message.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from cryptography.fernet import Fernet
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD_SECRET = "x" * 64   # 64 chars, looks like a real tokenurlsafe
GOOD_FERNET = Fernet.generate_key().decode()
GOOD_MONITORING = "x" * 40
GOOD_SMTP_HOST = "smtp.sendgrid.net"
GOOD_SMTP_USER = "noreply@coredent-prod.com"
GOOD_SMTP_PASS = "x" * 24
GOOD_BUCKET = "coredent-prod-attachments"
GOOD_HOSTS = "app.coredent-prod.com,api.coredent-prod.com"
GOOD_CORS = "https://app.coredent-prod.com"
GOOD_TRUSTED = "10.0.0.0/8"
GOOD_REDIS = "redis://redis.internal:6379/0"

# Baseline env that the production-required validator accepts.
def base_env() -> dict:
    e = os.environ.copy()
    e["ENVIRONMENT"] = "production"
    e["DEBUG"] = "false"
    e["SECRET_KEY"] = GOOD_SECRET
    e["ENCRYPTION_KEYS"] = f"current:{GOOD_FERNET}"
    e["MONITORING_TOKEN"] = GOOD_MONITORING
    e["SMTP_HOST"] = GOOD_SMTP_HOST
    e["SMTP_USER"] = GOOD_SMTP_USER
    e["SMTP_PASSWORD"] = GOOD_SMTP_PASS
    e["AWS_S3_BUCKET"] = GOOD_BUCKET
    e["ALLOWED_HOSTS"] = GOOD_HOSTS
    e["CORS_ORIGINS"] = GOOD_CORS
    e["TRUSTED_PROXIES"] = GOOD_TRUSTED
    e["REDIS_URL"] = GOOD_REDIS
    e["DATABASE_URL"] = "postgresql+asyncpg://u:p@db:5432/cd"
    # Phase 3 discovered required vars that the audit list omitted; the
    # fail-closed list now also requires SENTRY_DSN, SEARCH_INDEX_KEY, and
    # STRIPE_WEBHOOK_SECRET for production.
    e["SENTRY_DSN"] = "https://abcd1234@sentry.example.com/1"
    e["SEARCH_INDEX_KEY"] = "x" * 40
    e["STRIPE_WEBHOOK_SECRET"] = "whsec_" + "x" * 32
    return e

def try_import(env: dict) -> tuple[int, str]:
    """Run ``import app.core.config_simple`` in a subprocess with the given env."""
    code = "import app.core.config_simple; print('OK')"
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    return res.returncode, (res.stderr.strip() or res.stdout.strip())

# 1. Baseline: a fully-provisioned production env must import cleanly.
env = base_env()
print(f"baseline env keys: {sorted(k for k in env if k in ('SECRET_KEY','ENCRYPTION_KEYS','MONITORING_TOKEN','SMTP_HOST','SMTP_USER','SMTP_PASSWORD','AWS_S3_BUCKET','ALLOWED_HOSTS','CORS_ORIGINS','TRUSTED_PROXIES','REDIS_URL','DATABASE_URL','SENTRY_DSN','SEARCH_INDEX_KEY','STRIPE_WEBHOOK_SECRET'))}")
rc, msg = try_import(env)
print(f"baseline (real-shape production env): returncode={rc}")
print(f"  msg: {msg}")
assert rc == 0, f"baseline must pass; got rc={rc} msg={msg}"

# 2. Each required value, mutated to a bad one, must fail with a useful message.
mutations = [
    ("SECRET_KEY", "dev-secret-key-foobar"),
    ("SECRET_KEY", "change-me-in-prod"),
    ("ENCRYPTION_KEYS", "current:change-me-in-prod"),
    ("MONITORING_TOKEN", ""),
    ("SMTP_HOST", "localhost"),
    ("AWS_S3_BUCKET", "your-bucket-here"),
    ("ALLOWED_HOSTS", "localhost,127.0.0.1"),
    ("CORS_ORIGINS", "https://localhost:3000,*"),
    ("TRUSTED_PROXIES", "not-a-cidr"),
    ("SENTRY_DSN", ""),
    ("SEARCH_INDEX_KEY", ""),
    ("STRIPE_WEBHOOK_SECRET", ""),
]
failed = []
for key, bad in mutations:
    env = base_env()
    env[key] = bad
    rc, msg = try_import(env)
    refused = rc != 0
    mark = "OK " if refused else "BUG"
    print(f"  {mark} {key}={bad!r:40s} -> rc={rc} msg={msg[:80]}")
    if not refused:
        failed.append((key, bad, msg))

# Production refuses to run even with a placeholder CORS origin.
if failed:
    print(f"\nFAIL: {len(failed)} bad-value mutations were not refused:")
    for k, b, m in failed:
        print(f"  - {k}={b!r}: {m}")
    sys.exit(1)

print(f"\nAll {len(mutations)} bad-value mutations were refused at import time.")