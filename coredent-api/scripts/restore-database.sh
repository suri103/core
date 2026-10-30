#!/usr/bin/env bash
# ==============================================================================
# CoreDent PMS - Automated Database Restore & DR Verification Script
# Restores pg_dump backup, validates schema and data integrity.
# ==============================================================================
set -euo pipefail

RESTORE_FILE="${1:-/tmp/dr-test.dump}"

if [ ! -f "${RESTORE_FILE}" ]; then
  echo "Error: Restore file not found at ${RESTORE_FILE}" >&2
  exit 1
fi

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting database restore from ${RESTORE_FILE}..."

set +e
if [ -n "${DATABASE_URL:-}" ]; then
  pg_restore -d "${DATABASE_URL}" -c --if-exists "${RESTORE_FILE}"
else
  pg_restore -h "${DB_HOST:-localhost}" \
             -p "${DB_PORT:-5432}" \
             -U "${DB_USER:-postgres}" \
             -d "${DB_NAME:-coredent}" \
             -c --if-exists "${RESTORE_FILE}"
fi
RESTORE_EXIT=$?
set -e

# pg_restore exits non-zero on warnings (e.g. version mismatches) as well as
# real failures. A failed restore must NEVER look like a successful DR drill,
# so failures abort unless the operator explicitly opts into ignoring them.
if [ ${RESTORE_EXIT} -ne 0 ] && [ "${PGRESTORE_IGNORE_ERRORS:-0}" != "1" ]; then
  echo "Error: pg_restore exited with status ${RESTORE_EXIT}." >&2
  echo "Re-run with PGRESTORE_IGNORE_ERRORS=1 only if you have verified the" >&2
  echo "messages are benign warnings." >&2
  exit ${RESTORE_EXIT}
fi

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Database restore finished. Running verification tests..."
pytest tests/test_dr_recovery.py
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Disaster recovery verification passed successfully."
