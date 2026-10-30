#!/usr/bin/env python
"""
Backup and restore utilities for the CoreDent Postgres database.

Phase 3 hardening: the audit required a backup/restore story.
This script wraps ``pg_dump`` / ``pg_restore`` with explicit safety
rails so an operator (or the CI pipeline) cannot accidentally point at
the.

Subcommands
-----------
backup     Create a timestamped pg_dump custom-format archive in ``$BACKUP_DIR``.
restore    Restore a dump into a target database. Refuses to run
    against the production database URL unless the operator passes
    ``--confirm-production``.
verify     Verify an archive by reading its pg_restore table of contents.

Env vars
--------
DATABASE_URL        Postgres URL (required).
BACKUP_DIR          Directory for backups. Default: ./backups.
PG_DUMP_BIN         Path to ``pg_dump``. Default: ``pg_dump`` on PATH.
PG_RESTORE_BIN      Path to ``pg_restore``. Default: ``pg_restore`` on PATH.

Format note
-----------
The archive is ``pg_dump -Fc`` (a binary custom-format archive), written with a
``.dump`` extension and read back by ``pg_restore``. This matches the other
backup tooling in this repo (``scripts/backup-database.sh``,
``scripts/restore-database.sh``, ``docker-compose.prod.yml``) and the
``-SourceDump`` expected by ``scripts/backup-dr-drill.ps1``, so one artifact
works with every tool.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _is_production_url(url: str) -> bool:
    """Heuristic: a DATABASE_URL is 'production' when the host is not
    localhost / 127.0.0.1 and COREDENT_ALLOW_PRODUCTION_RESTORE is not set.
    Restore into production requires --confirm-production.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if os.getenv("COREDENT_ALLOW_PRODUCTION_RESTORE") == "1":
        return False
    return True


def _pg_args(url: str, *extra: str) -> list[str]:
    """Build pg_dump / pg_restore argv from a DATABASE_URL."""
    parsed = urlparse(url)
    args: list[str] = []
    if parsed.username:
        args += ["-U", parsed.username]
    if parsed.hostname:
        args += ["-h", parsed.hostname]
    if parsed.port:
        args += ["-p", str(parsed.port)]
    if parsed.password:
        os.environ["PGPASSWORD"] = parsed.password
    args += list(extra)
    if parsed.path.lstrip("/"):
        args += ["-d", parsed.path.lstrip("/")]
    return args


def cmd_backup(args: argparse.Namespace) -> int:
    backup_dir = Path(os.environ.get("BACKUP_DIR", "./backups")).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    url = os.environ["DATABASE_URL"]
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = backup_dir / f"coredent-{timestamp}.dump"

    pg_dump = os.environ.get("PG_DUMP_BIN", "pg_dump")
    if not shutil.which(pg_dump):
        print(f"ERROR: {pg_dump} not found on PATH", file=sys.stderr)
        return 2

    argv = [pg_dump, *(_pg_args(url)), "-Fc", "-f", str(out)]
    print(f"Running: {' '.join(argv)}")
    proc = subprocess.run(argv, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        print(f"ERROR: pg_dump exited {proc.returncode}", file=sys.stderr)
        # Never leave a partial archive behind: anything that later globs the
        # backup directory would treat a truncated file as a usable backup.
        out.unlink(missing_ok=True)
        return proc.returncode
    print(f"Backup written to {out}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    url = os.environ["DATABASE_URL"]
    if _is_production_url(url) and not args.confirm_production:
        print(
            "ERROR: refusing to restore into a non-localhost database "
            "without --confirm-production. This is a safety rail.",
            file=sys.stderr,
        )
        return 3

    pg_restore = os.environ.get("PG_RESTORE_BIN", "pg_restore")
    if not shutil.which(pg_restore):
        print(f"ERROR: {pg_restore} not found on PATH", file=sys.stderr)
        return 2

    backup_path = Path(args.backup_path)
    if not backup_path.exists():
        print(f"ERROR: backup file not found: {backup_path}", file=sys.stderr)
        return 4

    argv = [pg_restore, *(_pg_args(url)), "--clean", "--no-owner", str(backup_path)]
    print(f"Running: {' '.join(argv)}")
    proc = subprocess.run(argv, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        return proc.returncode
    print("Restore complete.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify an archive by reading its pg_restore table of contents.

    The archive is pg_dump's binary custom format, so the previous
    implementation - counting lines that start with "CREATE TABLE" - could
    never match anything and always reported ~0 tables. That is worse than
    having no verifier at all, because it looks like a real result.
    ``pg_restore --list`` reads the archive TOC without restoring anything.
    """
    backup_path = Path(args.backup_path)
    if not backup_path.exists():
        print(f"ERROR: backup file not found: {backup_path}", file=sys.stderr)
        return 4

    pg_restore = os.environ.get("PG_RESTORE_BIN", "pg_restore")
    if not shutil.which(pg_restore):
        print(f"ERROR: {pg_restore} not found on PATH", file=sys.stderr)
        return 2

    proc = subprocess.run(
        [pg_restore, "--list", str(backup_path)],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        print(
            f"ERROR: {backup_path} is not a readable pg_dump archive "
            f"(pg_restore --list exited {proc.returncode})",
            file=sys.stderr,
        )
        return proc.returncode

    lines = proc.stdout.decode("utf-8", errors="replace").splitlines()
    tables = [ln for ln in lines if " TABLE " in ln and "TABLE DATA" not in ln]
    data_sections = [ln for ln in lines if " TABLE DATA " in ln]

    db_name = ""
    for line in lines[:12]:
        if line.startswith(";") and "dbname:" in line:
            db_name = line.split("dbname:", 1)[1].strip()

    print(
        f"Archive OK: {len(lines)} TOC entries, {len(tables)} tables, "
        f"{len(data_sections)} table-data sections"
        + (f", dbname={db_name}" if db_name else "")
    )
    if not tables:
        print(
            "ERROR: archive lists no TABLE entries - refusing to treat this as a "
            "valid backup.",
            file=sys.stderr,
        )
        return 6
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="Create a pg_dump custom-format archive.")
    b.set_defaults(func=cmd_backup)

    r = sub.add_parser("restore", help="Restore a .dump archive into a target DB.")
    r.add_argument("backup_path", help="Path to a .dump backup file.")
    r.add_argument(
        "--confirm-production",
        action="store_true",
        help="Acknowledge that the target DATABASE_URL is production.",
    )
    r.set_defaults(func=cmd_restore)

    v = sub.add_parser("verify", help="Verify a backup file by table count.")
    v.add_argument("backup_path", help="Path to a .dump backup file.")
    v.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 5
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())