# CoreDent deployment runbook

CoreDent uses:

- Vercel for the Vite frontend in `coredent-style-main`
- Railway for the FastAPI backend and its PostgreSQL, Redis, ClamAV,
  Celery worker, and Celery Beat services

Do not process real patient data until Business Associate Agreements and
required compliance controls are active for every vendor that may handle PHI.

## Production domains

Replace these examples with the real domains:

- Frontend: `https://app.example.com`
- API: `https://api.example.com`
- Frontend API base: `https://api.example.com/api/v1`

## Railway API service

Connect the repository and configure:

```text
Root Directory: /coredent-api
Config File Path: /railway.json
Healthcheck Path: /health
```

Add PostgreSQL and Redis to the same Railway project and environment. Use
private reference variables:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

Add a private ClamAV service and configure:

```text
CLAMAV_HOST=${{ClamAV.RAILWAY_PRIVATE_DOMAIN}}
CLAMAV_PORT=3310
```

Required API production settings include:

```text
ENVIRONMENT=production
DEBUG=False
PORT=3000
RUN_MIGRATIONS_ON_START=false
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
ALLOWED_HOSTS=api.example.com,healthcheck.railway.app
SECRET_KEY=<generated random value>
ENCRYPTION_KEYS=current:<generated Fernet key>
MONITORING_TOKEN=<generated random value>
SENTRY_DSN=<backend Sentry DSN>
STRIPE_WEBHOOK_SECRET=<Stripe endpoint signing secret>
```

Use this API pre-deploy command:

```text
python -c "from start import run_migrations; run_migrations()"
```

## Railway background services

The worker uses the same repository, root directory, image, and necessary
variables as the API. It must not have a public domain.

```text
celery -A app.core.celery_app:celery_app worker -Q default,communications,reminders,emails -l info
```

Celery Beat must run with exactly one replica and no public domain:

```text
celery -A app.core.celery_app:celery_app beat -l info
```

PostgreSQL, Redis, and ClamAV must not have public HTTP domains.

## Vercel frontend

Import the same repository and configure:

```text
Root Directory: coredent-style-main
Framework: Vite
Build Command: npm run build
Output Directory: dist
```

Set this production environment variable:

```text
VITE_API_BASE_URL=https://api.example.com/api/v1
```

Optional frontend monitoring:

```text
VITE_SENTRY_DSN=<public frontend Sentry DSN>
```

Never place server credentials in a `VITE_*` variable. Vite embeds these
values in public browser code.

## Release checks

Run locally before promoting a release:

```powershell
cd coredent-style-main
npm run typecheck
npm run lint:ci
npm test
npm run build
npm audit

cd ..\coredent-api
python -m ruff check app tests
python -m pytest
pip-audit -r requirements.txt
```

After staging deployment:

```powershell
.\scripts\production-smoke.ps1 `
  -ApiOrigin https://api-staging.example.com `
  -FrontendOrigin https://app-staging.example.com
```

1. Confirm the API `/health` endpoint returns HTTP 200.
2. Confirm the frontend loads without browser console or CORS errors.
3. Exercise registration, login, logout, password reset, patient portal,
   appointments, document upload, and Stripe test payments.
4. Confirm ClamAV accepts a harmless file and rejects an EICAR test file.
5. Confirm Celery processes email/reminder jobs and Beat schedules each job
   only once.
6. Restore a PostgreSQL backup into a separate environment.
7. Confirm one clinic cannot read or alter another clinic's records.
8. Review audit logs and ensure monitoring does not capture PHI.

## Rollback

If a release fails:

1. Roll back the frontend deployment in Vercel.
2. Roll back the API deployment in Railway.
3. Do not reverse a database migration until its downgrade safety has been
   reviewed.
4. Restore a database backup only for confirmed data corruption, and preserve
   the affected database for incident investigation.
