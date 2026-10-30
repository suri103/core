# Railway Staging Setup — CoreDent (one-image, PROCESS_TYPE roles)

> Companion to `README_DEPLOYMENT.md` (production shape) and the ops scripts in
> `scripts/`. Staging must **mirror production** exactly; the only differences
> are the domain, the secret values, and `TRUSTED_PROXIES`.

**Goal:** a second Railway project `coredent-staging` with services
`api`, `worker`, `beat`, `Postgres`, `Redis`, `ClamAV`, plus one-off `release`.
Vercel project `coredent-staging-web` hosts the frontend.

```text
Railway project: coredent-staging

  api ------> Postgres (private ref)
  |  |------> Redis    (private ref)
  |  |------> ClamAV   (private ref)
  |  └─health: /health (300s timeout, advisory-lock migrations)
  worker ---> Postgres + Redis (same refs), NO public domain
  beat -----> Postgres + Redis (same refs), exactly 1 replica
  release --> Postgres (runs migrations, exits; driven manually)

  Vercel project: coredent-staging-web → app-staging.example.com
```

---

## 1. Create the project and services (Railway UI, ~15 min)

1. **New project** ← `suraiamkapooram10008-lgtm/coredentist`, branch `master`, name it
   `coredent-staging`. Keep production on its own project — staging must never
   share a Postgres/Redis with prod.
2. **API service**: same repo. Root directory `/coredent-api`, config `railway.json`
   (builds `coredent-api/Dockerfile`, starts `python /app/start.py`,
   healthcheck `/health`, 300s timeout for advisory-lock migrations).
3. **Add databases**: `Postgres` (PostgreSQL 16) + `Redis`. No public domains on
   either; everything talks over `${{...RAILWAY_PRIVATE_DOMAIN}}` refs.
4. **Add ClamAV** as a private service, same as production.
5. **Duplicate the API service twice** (same repo/image/vars):
   - `worker` — NO public domain.
   - `beat` — NO public domain, **exactly 1 replica** (two beats double-fire schedules).
6. (Optional, recommended) **One-shot `release` service** run manually before deploys
   (`PROCESS_TYPE=release`), or let the API role migrate at boot — the repo's
   advisory-lock design makes both safe, but the dedicated job is the cleaner log.

## 2. Service roles — one image, `PROCESS_TYPE` env per service

Your `coredent-api/start.py` already switches roles; set per service:

| Service | `PROCESS_TYPE` | Public domain? | Replicas |
|---|---|---|---|
| api | `web` (default) | YES (`api-staging.example.com`) | 1–2 |
| worker | `worker` | **NO** | 1 |
| beat | `beat` | **NO** | **exactly 1** |
| release | `release` | **NO** | 0 (run on demand) |

Also set `RUN_MIGRATIONS_ON_START=true` (default) on `api`; set it
`RUN_MIGRATIONS_ON_START=false` on `worker`/`beat` (DDL belongs to web/release only).

## 3. Env vars — copy this table, generate fresh secrets per env

Shared (api + worker + beat + release). Never share values between staging and prod.

```text
ENVIRONMENT=staging
DEBUG=False
PORT=3000
RUN_MIGRATIONS_ON_START=true            # false on worker/beat only
DATABASE_URL=${{Postgres.DATABASE_URL}}          # auto-normalised postgres:// -> postgresql://
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
CLAMAV_HOST=${{ClamAV.RAILWAY_PRIVATE_DOMAIN}}
CLAMAV_PORT=3310
FRONTEND_URL=https://app-staging.example.com
CORS_ORIGINS=https://app-staging.example.com
ALLOWED_HOSTS=api-staging.example.com,healthcheck.railway.app
TRUSTED_PROXIES=<Railway edge range for staging>
SECRET_KEY=<generate: 64 hex chars, staging-only>
ENCRYPTION_KEYS=current:<generated Fernet key>   # never reuse prod keys
MONITORING_TOKEN=<generate random, staging-only>
SENTRY_DSN=<backend staging Sentry DSN>
STRIPE_PUBLISHABLE_KEY=<Stripe TEST publishable key>
STRIPE_SECRET_KEY=<Stripe TEST secret key>
STRIPE_WEBHOOK_SECRET=<staging endpoint signing secret>
SMTP_HOST= / SMTP_PORT= / SMTP_USER= / SMTP_PASSWORD=   # Mailtrap/SendGrid test inbox
TWILIO_ACCOUNT_SID= / TWILIO_AUTH_TOKEN=   # Twilio test credentials (no SMS sent by smoke)
AWS_S3_BUCKET=<staging-only PRIVATE bucket>  # must be private + access-controlled
AWS_REGION=<region>
VITE_API_BASE_URL=https://api-staging.example.com/api/v1   # Vercel project var
VITE_SENTRY_DSN=<frontend staging Sentry DSN, optional>
```

Quick generators (run locally, paste results):

```powershell

## 6. Validation runs (the actual gate)

Run in this order; everything here already exists in `scripts/`:

```powershell
# 1) Public smoke (health, headers, CORS)
.\scripts\production-smoke.ps1 `
  -ApiOrigin https://api-staging.example.com `
  -FrontendOrigin https://app-staging.example.com

# 2) Live integrations (Stripe test keys, SMTP EHLO, S3 private, Redis,
#    Celery ping, Sentry, ClamAV) - SKIP-friendly, never prints secrets
$env:STRIPE_SECRET_KEY='sk_test_...'; $env:SMTP_HOST='...'
.\scripts\live-integration-smoke.ps1 --with-celery

# 3) ClamAV behaviour: upload harmless file (accepted) + EICAR test file
#    (rejected) through the patient-documents UI or API.

# 4) Multi-tenant isolation: two clinics, attempt cross-tenant read/write,
#    expect 403s + TenantGuard rejections (mirrors tests/test_tenant_isolation.py).
```

## 7. First DR drill (the compliance evidence)

Use the companion runbook + runner — do it **on staging first**, never prod:

1. Produce a full dump of the staging Postgres (Railway backup or `pg_dump`).
2. Provision a **scratch** Postgres (Railway throwaway DB in the same project).
3. Run the checklist + measured restore:
   ```powershell
   # Checklist to follow step-by-step:
   # scripts/backup-dr-drill-checklist.md
   .\scripts\backup-dr-drill.ps1 `
     -SourceDump <path-to-latest-staging.dump> `
     -TargetPgDbUrl "postgresql://dr:dr@<scratch-host>:5432/dr" `
     -HealthUrl "http://localhost:8000/health"
   ```
   It refuses to target prod, times/maps RTO (≤4h gate), checks table counts,
   and probes that audit write-once still enforces after restore.
4. Tear down the scratch DB. Write the dated entry into `docs/dr-drill-log.md`
   (create it): date, backup sha, table counts, measured RTO, sign-off initials.

## 8. Promote-to-prod rules (write these down before you need them)

- Prod deploy only after staging gate passes: smoke + integrations + (monthly) DR drill.
- Roll back frontend in Vercel / API in Railway; never reverse a migration
  without reviewed downgrade safety.
- Restore a backup only for confirmed corruption; preserve the affected DB for
  incident investigation (same rule as `README_DEPLOYMENT.md`).

## 9. Monthly standing tasks

1. DR drill (section 7) — first Tuesday, evidence in `dr-drill-log.md`.
2. `pip-audit` + `npm audit` fresh; rotate nothing silently.
3. Review audit logs + confirm monitoring captures no PHI.
4. Confirm `beat` still exactly 1 replica after any Railway resync.

python -c "import secrets; print(secrets.token_hex(32))"        # SECRET_KEY / MONITORING_TOKEN
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEYS value
```

## 4. Vercel staging web (5 min)

New Vercel project ← same repo: Root `coredent-style-main`, Framework Vite,
Build `npm run build`, Output `dist`, domain `app-staging.example.com`,
`VITE_API_BASE_URL=https://api-staging.example.com/api/v1`.
**Never** put server secrets in `VITE_*` (they ship in browser code).

## 5. First-boot checklist (once, ~20 min)

1. Deploy `release` (or watch `api` boot): confirm `alembic upgrade head` completes
   under the advisory lock in logs.
2. `GET https://api-staging.example.com/health` → 200, `"status": "healthy"`,
   `"database": "connected"`.
3. Confirm `worker` logs show queues `default,communications,reminders,emails`;
   `beat` logs show each schedule registered **once**.
4. Confirm Postgres/Redis/ClamAV have **no public domains**.
5. Register one clinic, create one patient, upload one file, send one test email
   to yourself. Delete nothing yet — you need live rows for step 6.
