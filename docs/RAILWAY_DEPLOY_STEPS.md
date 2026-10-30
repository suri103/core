# CoreDent — Railway + Vercel Deployment: Step-by-Step Checklist

> This is the exact hands-on sequence to stand up staging (and, later, production)
> with `suraiamkapooram10008-lgtm/coredentist`. It is distilled from
> `README_DEPLOYMENT.md`, `docs/RAILWAY_STAGING_SETUP.md`, `railway.json`,
> `coredent-api/start.py`, and the fail-closed validation in
> `coredent-api/app/core/config_simple.py` (lines ~304–488).
>
> **Important:** the backend refuses to boot in ANY non-local environment until
> every variable below is real. `staging` is treated exactly like `production`
> (see `_LOCAL_ENVIRONMENTS = {development, dev, test, testing, local}`). So the
> app will keep crash-looping until ALL of section 3 is filled correctly — do not
> panic, that is the safety net working.

---

## 0. Prereqs (one-time, ~10 min)

- [ ] GitHub repo `suraiamkapooram10008-lgtm/coredentist` has `master` pushed.
- [ ] We are deploying **Railway-only** (no Supabase needed — see
      `RAILWAY_STAGING_SETUP.md` intro).
- [ ] You have accounts: Railway, Vercel, Stripe (test mode), Sentry,
      SendGrid/Mailtrap (or any SMTP), AWS S3 (or compatible), Twilio (optional).
- [ ] A domain you control so you can create `api.example.com` / `app.example.com`.
      (No domain yet? Use Railway/Vercel default `*.up.railway.app` /
      `*.vercel.app` URLs for a first pass — you'll re-set
      ALLOWED_HOSTS/CORS later.)

---

## 1. Create the Railway project (~15 min)

1. Sign in at https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. Select `suraiamkapooram10008-lgtm/coredentist`, branch `master`.
3. Name the project `coredent-prod` (or `coredent-staging`). **Keep staging and
   prod in separate Railway projects** so they can never share a DB.
4. Add a **PostgreSQL** service (version 16) — Railway sets
   `Postgres.RAILWAY_DATABASE_URL` / `Postgres.DATABASE_URL` automatically.
5. Add a **Redis** service — Railway sets `Redis.RAILWAY_TCP_URL` / `Redis.REDIS_URL`.
6. Add **ClamAV** — Railway marketplace has an official template; it exposes
   `ClamAV.RAILWAY_PRIVATE_DOMAIN` (port 3310). No public domain.

All three are **container services with NO public domain** — they're internal.

---

## 2. Deploy the API service (the backend container)

1. In the same project → **Deploy from GitHub repo** → pick the same repo.
   Railway detects `railway.json` at repo root which targets
   `coredent-api/Dockerfile`.
2. Rename the service to `api`.
3. Settings for `api`:
   - Root Directory: `/coredent-api`
   - Start Command: `python /app/start.py` (already in `railway.json`)
   - Healthcheck path: `/health`, timeout **300s** (migrations under advisory
     lock can take a while on cold start)
   - **Add a public domain** → `https://api.example.com`
4. **Before first deploy**, set Variables (section 3) — otherwise the container
   fails the config gate and restarts.
5. Deploy once. Watch logs: it should print
## 3. Variables — set these BEFORE the first healthy boot

`ENVIRONMENT=production` (or `staging`). **This is the non-negotiable list the
code requires; boot fails with a red error until every one is present.**

### Required by the fail-closed config gate (`config_simple.py`)

| Variable | Value | Where from |
|---|---|---|
| `ENVIRONMENT` | `production` (or `staging`) | you |
| `SECRET_KEY` | 32+ chars random | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ENCRYPTION_KEYS` | `current:<Fernet>` (comma for rotation) | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SEARCH_INDEX_KEY` | 32+ chars independent random | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `KMS_BACKEND` | `env` (start); `aws` only if you have AWS KMS + encrypted data key | you |
| `SENTRY_DSN` | from sentry.io project | Sentry |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from Stripe dashboard → webhooks | Stripe |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (or `${{Redis.RAILWAY_TCP_URL}}`) | Railway reference |
| `MONITORING_TOKEN` | 32+ chars random | you |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | from SendGrid/Mailtrap; NOT `localhost`, no placeholders | provider |
| `AWS_S3_BUCKET` | your **private** S3 bucket name (no placeholder) | AWS |
| `ALLOWED_HOSTS` | `api.example.com` (comma-separated; add `healthcheck.railway.app`) | you |
| `CORS_ORIGINS` | `https://app.example.com` (exact origins, NO `*`, no `localhost`) | you |
| `TRUSTED_PROXIES` | Railway edge CIDR (see Railway docs/support) | Railway |

### Strongly recommended (found in `.env.production.example`)

`DEBUG=False`, `PORT=3000`, `DATABASE_POOL_SIZE=20`, `DATABASE_MAX_OVERFLOW=10`,
`FRONTEND_URL=https://app.example.com`, `STRIPE_SECRET_KEY=sk_test_...`,
`STRIPE_PUBLISHABLE_KEY=pk_test_...`, `ACCESS_TOKEN_EXPIRE_MINUTES=15`,
`REFRESH_TOKEN_EXPIRE_DAYS=7`, `AUDIT_LOG_ENABLED=true`,
`MAX_UPLOAD_SIZE=10485760`, `ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png,doc,docx`,
`EMAIL_PROVIDER=smtp`, `SMS_PROVIDER=twilio`,
`TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY` (or IAM role).

**Use Railway `${{...}}` reference variables** (`${{Postgres.DATABASE_URL}}`,
`${{Redis.REDIS_URL}}`) so secrets aren't typed literally, and never commit
`.env.production` to git. Do NOT copy `coredent-api/.env.production.example`
placeholder values verbatim — the gate will catch them.
   `Executing: alembic upgrade head` then `Uvicorn running on 0.0.0.0:3000`.
## 4. Celery worker + beat (same image, different PROCESS_TYPE)

Duplicate the `api` service TWICE (same repo/image), rename to `worker` and `beat`.
Set on both: same Variables as API with `RUN_MIGRATIONS_ON_START=false` and
`PROCESS_TYPE=worker|beat`.

- **worker**: `PROCESS_TYPE=worker` (start.py handles `-Q default,communications,
  reminders,emails`). NO public domain.
- **beat**: `PROCESS_TYPE=beat` (start.py starts `celery beat`). NO public domain.
  **Exactly one replica** — two beats double-fire schedules.

Both must point at the same Postgres + Redis + ENCRYPTION_KEYS as API (a worker
that can't decrypt PHI corrupts on write).

### Gotchas that will crash-loop the worker if missed

1. **Clear the Healthcheck Path.** Railway's Deploy → Healthcheck Path defaults
   to `/health`, and `railway.json` at the repo root sets it too. Worker and beat
   have **no HTTP listener**, so an HTTP healthcheck can never pass: the container
   is killed on every boot and the deploy is marked failed. Leave the field empty
   for both. The image's own `healthcheck.py` is PROCESS_TYPE-aware (broker PING
   for worker/beat) and is the probe that should be used.
2. **No public domain, and no cron schedule on beat.** Beat is a long-running
   scheduler, not a one-shot job.
3. **Watch the connection budget.** `DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW`
   applies per replica, and web + worker + beat are three replicas:
   3 × (5 + 5) = 30 connections to the same Postgres.

### Verify the worker is actually doing work

The failure mode here is silent — every service shows Online while no scheduled
job ever runs.

```bash
# Every beat entry must name a registered task and be routed to a queue the
# worker consumes. Exits non-zero on a problem; also runs in CI.
cd coredent-api
python scripts/check_celery_wiring.py

# Then confirm the worker is consuming and beat is scheduling:
railway logs -s worker | findstr "celery@"
railway logs -s beat   | findstr "Scheduler"
```

A worker with no `celery@` ready line, or a beat that never logs a schedule, is
not running the jobs it appears to be running.

---

## 5. Vercel frontend (~5 min)

1. vercel.com → **Add New Project** → Import same repo.
2. Root Directory: `coredent-style-main`; Framework Vite; Build `npm run build`;
   Output `dist`.
3. Environment Variables: `VITE_API_BASE_URL=https://api.example.com/api/v1` —
   only the public API origin; never secrets.
4. Add domain `https://app.example.com` → set `CORS_ORIGINS` +
   `FRONTEND_URL=https://app.example.com` on Railway to match.

---

## 6. Verify (in order)

1. `curl https://api.example.com/health` → `{"status":"healthy","database":"connected"}`
2. Open `https://app.example.com` — no CORS/console errors.
3. `POST /api/v1/auth/register` → register a practice.
4. `POST /api/v1/auth/login` → get JWT; then `GET /api/v1/auth/me` → 200.
5. Create a patient, appointment, invoice, payment (test mode only).
6. Upload → ClamAV accepts harmless, rejects EICAR.
7. Confirm worker logs consume tasks + Beat picked up schedules once.
8. `.\scripts\production-smoke.ps1 -ApiOrigin https://api.example.com -FrontendOrigin https://app.example.com`
9. Record Stripe webhook secret (`whsec_...`, test mode) into
   `STRIPE_WEBHOOK_SECRET` correctly.

---

## 7. Promote-to-prod / rollback rules

- Only promote a release that passed section 6 + `.\scripts\gate-production.ps1`.
- Frontend rollback: Vercel → Redeploy previous deployment.
- API rollback: Railway → Deploy previous image / `git revert` + redeploy.
- Never reverse a migration without a reviewed `downgrade` path.
- Restore DB only for confirmed corruption; keep the broken DB for forensics.

---

## 8. What still needs a human (not code)

- [ ] Sign BAAs: Railway, Vercel, Sentry, Stripe, Twilio, SendGrid/Mailtrap, AWS.
- [ ] Attorney review of Privacy/Terms/DPA + consent flows.
- [ ] SRA + incident-response drill (runbooks exist; run them).
- [ ] Pen-test engagement (`docs/PENTEST_SCOPE.md` exists).
- [ ] Backup/DR first drill (runbooks + scripts/backup-dr-drill.ps1).