#!/usr/bin/env bash
#
# CoreDent - offsite PostgreSQL backup job.
#
# Runs as a one-shot Railway cron service (see backup/README.md). It is NOT
# part of the API image: it needs a pg_dump that matches the server's major
# version, and the API image's Debian base only ships postgresql-client 15
# while the database is PostgreSQL 16.
#
# Contract:
#   * Exits non-zero on ANY failure, so the platform marks the run failed
#     instead of silently recording a green run with no backup.
#   * Validates the archive with pg_restore --list BEFORE uploading it, so a
#     truncated or corrupt dump is never published as a restorable backup.
#   * Uploads <stamp>.dump + <stamp>.dump.sha256, then the rolling latest.dump
#     pointer that docs/BACKUP_DR_RUNBOOK.md and scripts/backup-dr-drill.ps1
#     expect.
#
# Required env:
#   DATABASE_URL        PostgreSQL URL. On Railway: ${{Postgres.DATABASE_URL}}
#   BACKUP_S3_BUCKET    Dedicated backup bucket (NOT the uploads bucket).
# Optional env:
#   BACKUP_S3_PREFIX    Key prefix. Default: database
#   AWS_REGION          Default: us-east-1
#   BACKUP_SSE          Server-side encryption. Default: AES256
set -euo pipefail

log() { printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-database}"
AWS_REGION="${AWS_REGION:-us-east-1}"
BACKUP_SSE="${BACKUP_SSE:-AES256}"

# A SQLite URL here means the job was misconfigured against a dev database.
# Backing that up would upload a useless file and, worse, look like success.
case "$DATABASE_URL" in
  postgres://*|postgresql://*) ;;
  *) die "DATABASE_URL is not a PostgreSQL URL; refusing to run" ;;
esac

workdir="$(mktemp -d)"
# Always remove the local copy: a backup that lingers on the host is a
# readable copy of the whole database sitting outside the encrypted bucket.
trap 'rm -rf "$workdir"' EXIT

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$workdir/coredent_${stamp}.dump"

log "pg_dump -> coredent_${stamp}.dump"
pg_dump --format=custom --no-owner --no-privileges -f "$archive" "$DATABASE_URL" \
  || die "pg_dump failed"

[ -s "$archive" ] || die "pg_dump produced an empty archive"

# Prove the archive is readable before it is trusted as a backup. Without
# this, a dump truncated by a full disk or a killed process uploads happily.
pg_restore --list "$archive" >/dev/null 2>&1 \
  || die "archive is not a readable pg_dump file; refusing to upload"

table_entries="$(pg_restore --list "$archive" | grep -c ' TABLE ' || true)"
log "archive verified: ${table_entries} table entries"
[ "${table_entries:-0}" -gt 0 ] || die "archive lists no tables; refusing to upload"

sha="$(sha256sum "$archive" | awk '{print $1}')"
printf '%s  %s\n' "$sha" "coredent_${stamp}.dump" > "${archive}.sha256"

remote="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}"
log "uploading to ${remote}/ (sse=${BACKUP_SSE})"

aws s3 cp "$archive" "${remote}/coredent_${stamp}.dump" \
  --sse "$BACKUP_SSE" --only-show-errors --region "$AWS_REGION"
aws s3 cp "${archive}.sha256" "${remote}/coredent_${stamp}.dump.sha256" \
  --sse "$BACKUP_SSE" --only-show-errors --region "$AWS_REGION"
aws s3 cp "$archive" "${remote}/latest.dump" \
  --sse "$BACKUP_SSE" --only-show-errors --region "$AWS_REGION"

log "done: ${remote}/coredent_${stamp}.dump (sha256 ${sha})"
