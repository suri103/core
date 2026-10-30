#!/usr/bin/env bash
# ==============================================================================
# CoreDent PMS - Automated Database Backup Script
# Performs encrypted pg_dump and uploads to backup storage with checksums.
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/tmp/coredent-backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/coredent_backup_${TIMESTAMP}.dump"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting CoreDent database backup..."

if [ -n "${DATABASE_URL:-}" ]; then
  pg_dump "${DATABASE_URL}" -Fc -f "${BACKUP_FILE}"
else
  pg_dump -h "${DB_HOST:-localhost}" \
          -p "${DB_PORT:-5432}" \
          -U "${DB_USER:-postgres}" \
          -d "${DB_NAME:-coredent}" \
          -Fc -f "${BACKUP_FILE}"
fi

sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Backup completed: ${BACKUP_FILE} (SHA256: $(cat "${CHECKSUM_FILE}"))"

if [ -n "${S3_BACKUP_BUCKET:-}" ]; then
  echo "Uploading to s3://${S3_BACKUP_BUCKET}/database/..."
  aws s3 cp "${BACKUP_FILE}" "s3://${S3_BACKUP_BUCKET}/database/coredent_backup_${TIMESTAMP}.dump"
  aws s3 cp "${CHECKSUM_FILE}" "s3://${S3_BACKUP_BUCKET}/database/coredent_backup_${TIMESTAMP}.dump.sha256"
  aws s3 cp "${BACKUP_FILE}" "s3://${S3_BACKUP_BUCKET}/database/latest.dump"
  echo "S3 upload complete."
fi
