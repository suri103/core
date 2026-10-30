"""Phase 3 check: FK columns without indexes in the migrated schema.

Unindexed foreign keys force full scans on every tenant-scoped join/filter.
Run against an alembic-migrated SQLite build (same DDL semantics as PG for
index presence). Exits non-zero when hot FK columns are unindexed.
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SECRET_KEY", "index-check-key-not-for-production-usage")
os.environ.setdefault("ENCRYPTION_KEY", "ojgJ3oQf7At2eiaGVqzSAitO_8dokW47KIPT_0NB8-g=")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ENVIRONMENT", "test")

db_path = Path(".idx-check.sqlite")
if db_path.exists():
    db_path.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.base import Base  # noqa: E402

config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
command.upgrade(config, "head")

conn = sqlite3.connect(db_path)

missing = []
for table in Base.metadata.sorted_tables:
    rows = conn.execute(f"PRAGMA table_info({table.name})").fetchall()
    if not rows:
        continue
    existing_cols = {row[1] for row in rows}
    indexed_cols: set[str] = set()
    for idx in conn.execute(f"PRAGMA index_list({table.name})").fetchall():
        idx_name = idx[1]
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx_name})").fetchall()]
        indexed_cols.update(cols)
    for fk in table.foreign_keys:
        col = fk.parent.name
        if col in existing_cols and col not in indexed_cols:
            missing.append(f"{table.name}.{col} -> {fk.target_fullname}")

conn.close()
db_path.unlink(missing_ok=True)

# Columns that only appear as (rare) FKs but are never used in WHERE/JOIN
# paths can be tolerated; everything here is a documented exception with a
# reason. Keep this list short and justified.
ALLOWED_UNINDEXED = {
    # usage_records.timestamp is range-scanned, but the table is
    # subscription-scoped via subscription_id which IS indexed.
}

hot = [m for m in missing if m.split(".")[0] not in {
    # tables whose unindexed FKs are acceptable (see notes above)
}]
if hot:
    print("UNINDEXED FOREIGN KEYS (candidate missing indexes):")
    for m in hot:
        print(f"  {m}")
    sys.exit(1)

print("All foreign keys are indexed.")
