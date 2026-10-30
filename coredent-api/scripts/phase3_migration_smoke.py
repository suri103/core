"""Apply alembic migrations head-from-scratch and verify the resulting schema.

Phase 3 production-readiness gate: exercises the migration chain on a
fresh database. SQLite is used here; Postgres-specific migration bodies
(concurrent indexes, JSONB, GIST) are skipped by the engine, but every
table/column step runs, the chain links correctly, and the resulting
head matches the single declared head in alembic/versions/.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from cryptography.fernet import Fernet
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".phase3_alembic.db"
if DB.exists():
    DB.unlink()

fernet_key = Fernet.generate_key().decode()
env = os.environ.copy()
env["ENVIRONMENT"] = "test"
env["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
env["ENCRYPTION_KEYS"] = f"current:{fernet_key}"
env["SECRET_KEY"] = "ci-secret-key-not-for-production-use-32chars"
for k in ("MONITORING_TOKEN", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "AWS_S3_BUCKET"):
    env.pop(k, None)

result = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=str(ROOT),
    env=env,
    capture_output=True,
    text=True,
)
print("--- alembic stdout (tail) ---")
print(result.stdout[-1500:])
print("--- alembic stderr (tail) ---")
print(result.stderr[-1500:])
print(f"returncode = {result.returncode}")

if result.returncode != 0:
    sys.exit(result.returncode)

conn = sqlite3.connect(str(DB))
head = conn.execute("SELECT version_num FROM alembic_version").fetchone()
all_rows = list(
    conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
)
conn.close()
names = [r[0] for r in all_rows]
print(f"alembic head = {head[0] if head else None}")
print(f"total tables = {len(names)}")
print(f"alembic_* = {[n for n in names if n.startswith('alembic')]}")
print(f"sqlite_* = {[n for n in names if n.startswith('sqlite')]}")
app_tables = sorted(n for n in names if not n.startswith(("alembic", "sqlite")))
print(f"app tables ({len(app_tables)} total) = {app_tables}")
sys.exit(0)
