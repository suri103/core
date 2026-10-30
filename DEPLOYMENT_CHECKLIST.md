# Deployment Checklist — CoreDent PMS

Status: Phase 3 production-readiness review, 2026-08-21.
Backend: `coredent-api` (FastAPI, Celery, Railway/Postgres). Frontend:
`coredent-style-main` (React/Vite, Vercel or static host).

---

## 0. Read this first

- **Migrations should run ONLINE** (`alembic upgrade head`) so data-dependent
  safety checks (duplicate detection, backfills) run against the live data.
  Offline rendering (`alembic upgrade head --sql`) is also complete: every
  revision emits static DDL, and data-dependent checks that cannot run during
  rendering are embedded as `RAISE WARNING` advisories in the generated
  script — read them before applying the script to a database with history.
- **Boot is fail-closed.** In any non-local environment the API refuses to
  start unless every required secret/external service is configured
  (`app/core/config_simple.py:256-354`). A boot that succeeds is a boot that
  has been validated.

## 1. Environment variables (Railway → Variables)

Required (validation errors name each one at boot):

| Var | Notes |
|---|---|
| `ENVIRONMENT` | `production` (anything outside dev/test set triggers full validation) |
| `SECRET_KEY` | ≥32 chars, unique per environment; never the committed dev value |
| `ENCRYPTION_KEY` or `ENCRYPTION_KEYS` | Fernet key(s); rotate via keyring (`python -c "from app.core.encryption import generate_key; print(generate_key())"`) |
| `SEARCH_INDEX_KEY` | ≥32 chars, INDEPENDENT secret (not derived from the Fernet key); HMACs patient search indexes |
| `KMS_BACKEND` / `AWS_KMS_KEY_ARN` | Optional; `aws` backend is validated at boot (ARN + `aws:` entry in `ENCRYPTION_KEYS` required) |
| `DATABASE_URL` | Postgres. `postgres://` scheme accepted and normalized |
| `REDIS_URL` | Required: rate limiting + Celery broker/backend |
| `SENTRY_DSN` | Required: no DSN = zero error visibility |
| `STRIPE_WEBHOOK_SECRET` | Required: payment webhooks refuse to process without it |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Required: password reset, verification, reminders depend on it |
| `AWS_S3_BUCKET` (+ keys) | Required: file/image uploads |
| `ALLOWED_HOSTS` | Comma-separated prod domains (Host-header attack guard) |
| `CORS_ORIGINS` | Explicit origins only — wildcard `*` now fails boot |
| `MONITORING_TOKEN` | Header token for `/metrics` |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Optional; fall back to REDIS_URL |

Placeholder-looking values (`example.com`, `changeme`, `your-*`) are
rejected at boot by design.

## 2. Pre-deploy gates (CI runs these; verify green before promoting)

- [ ] `ruff check app tests`
- [ ] `pip-audit -r requirements.txt`
- [ ] Fresh-database migration rehearsal: empty Postgres, `alembic upgrade head`
      (staging first — see §6)
- [ ] `pytest tests` (full suite)
- [ ] Frontend: `npm run typecheck`, `npm run lint`, `npm test -- --run`,
      `npm run build`
- [ ] `npm audit --omit=dev`

Local equivalents all green as of 2026-08-21 (see Phase 3 report).

## 3. Deploy sequence

1. **Backup**: `scripts/backup-database.sh` (verify checksum + S3 upload).
2. **Migrations**: `alembic upgrade head` against staging → smoke test →
   then production. New revisions in this release:
   - `b8e4f6a2c9d7` reminder uniqueness (+ dedupe of existing duplicates)
     and `patient_images.share_expires_at`
   - `c7d8e9f0a1b2` additive schema-drift repair (marketing tables,
     conversations/document-signatures columns, referrals.completed_at,
     soft-delete columns) — **additive only, no data loss**
   - `d9e0f1a2b3c4` ~140 FK indexes — brief per-index locks; for any table
     already >10⁶ rows, pre-create with `CREATE INDEX CONCURRENTLY`
3. **Deploy API** (Railway auto-runs `start.py`; workers:
   `celery -A celery_worker.celery_app worker -Q default,communications,reminders,emails`,
   beat: `celery -A celery_worker.celery_app beat`). The `reminders` queue is
   required — appointment reminder tasks route there.
4. **Deploy frontend** after API is healthy.

## 4. Smoke tests (post-deploy, ≤5 min)

- [ ] `GET /health` → 200 with `"database": "healthy"` (or equivalent)
- [ ] `GET /metrics` without token → 403; with `X-Monitoring-Token` → 200
- [ ] Login → dashboard loads patients list (exercises auth + tenant scoping)
- [ ] Create an invoice → appears with 2dp totals; cancel it → audit log row
- [ ] Trigger a password-reset email (exercises SMTP)
- [ ] Sentry receives a test event (or confirm recent real events flowing)
- [ ] Celery: `celery -A celery_worker.celery_app inspect registered` shows
      tasks from `app.core.tasks` AND `app.core.communication_tasks`;
      beat log shows schedule entries firing

## 5. Observability

- Structured JSON logs w/ PHI redaction (`app/main.py`), Sentry w/
  redaction, `/health` (DB check), protected `/metrics`.
- Alerts to configure (provider-side): error-rate spike, /health failures,
  Redis unavailable, Celery queue depth, DB connections.

## 6. Rollback plan

1. **App rollback**: redeploy previous image/commit (Railway → Deployments
   → Redeploy). Safe because every schema change in this release is
   ADDITIVE; older code ignores new columns/tables/indexes.
2. **Migration rollback** (only if a new revision itself misbehaves):
   `alembic downgrade <previous>` — `c7d8e9f0a1b2` drops only the tables it
   created; `d9e0f1a2b3c4` only its indexes; `b8e4f6a2c9d7` removes the
   share-expiry column + unique index (duplicate reminders may reappear —
   acceptable transiently). Do NOT roll back after real traffic has written
   to new columns unless you accept losing those rows.
3. **Data disaster**: `scripts/restore-database.sh <backup.dump>` (fails
   hard on restore errors unless `PGRESTORE_IGNORE_ERRORS=1`), followed by
   `pytest tests/test_dr_recovery.py`. RPO/RTO targets and drill history:
   `coredent-api/docs/BACKUP_DR_RUNBOOK.md`.

## 7. Known follow-ups (non-blocking)

- Rehearse the full chain on a real staging Postgres before first prod
  deploy (local verification used SQLite + PG-dialect SQL rendering).
- Marketing module models now exist end-to-end but no backend routes
  consume them yet (frontend page uses mocks) — either wire or hide.
- Done (2026-09-01, revision f1a3c5e7d9b2): dead
  `email_verification_token_hash` columns dropped from `users` and
  `online_bookings` (never mapped by any model).
