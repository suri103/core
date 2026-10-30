# CoreDent — Production Deployment

This is the single source of truth for going live. Supersedes every other markdown file in this repo.

## 1. Generate secrets locally

```powershell
# SECRET_KEY (min 32 chars, URL-safe)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# MONITORING_TOKEN (for /metrics endpoint)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save these three values. They never go into git.

## 2. Set up Sentry (required for production visibility)

1. Create a free project at https://sentry.io (Python for backend, Browser for frontend).
2. Copy the DSN for each.
3. You'll paste these into Railway env vars in step 4.

If Sentry is skipped, the backend boots fine and logs a warning — you just won't see production errors.

## 3. Create a Postgres database

Railway: Click "New" → "Database" → "PostgreSQL". It auto-sets `DATABASE_URL`.

## 4. Backend env vars (Railway service: coredent-api)

Required:

```
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<from step 1>
ENCRYPTION_KEY=<from step 1>
DATABASE_URL=<auto-set by Railway Postgres>
ALLOWED_HOSTS=api.yourdomain.com
CORS_ORIGINS=https://app.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
```

Strongly recommended:

```
SENTRY_DSN=<backend DSN from step 2>
REDIS_URL=<Railway Redis addon>
MONITORING_TOKEN=<from step 1>
```

Needed for full functionality:

```
# Email (pick one provider)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<sendgrid api key>
SMTP_FROM=noreply@yourdomain.com

# File storage
AWS_ACCESS_KEY_ID=<...>
AWS_SECRET_ACCESS_KEY=<...>
AWS_S3_BUCKET=coredent-prod
AWS_REGION=us-east-1

# Payments (if applicable)
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Insurance EDI (if applicable)
DXC_API_KEY=<...>
DXC_API_SECRET=<...>
```

## 5. Frontend env vars (Railway service: coredent-web)

```
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
VITE_ENABLE_DEMO_MODE=false
VITE_DEV_BYPASS_AUTH=false
VITE_SENTRY_DSN=<frontend DSN from step 2>
VITE_SENTRY_ENVIRONMENT=production
```

Leave `VITE_SENTRY_DSN` blank if you skipped step 2 — placeholder values are auto-rejected.

## 6. Deploy

Railway auto-deploys on `git push` to the tracked branch. The backend's `start.py` runs `alembic upgrade head` before starting uvicorn. If migrations fail in production, the app refuses to start (by design).

## 7. Create the first owner account

SSH into Railway shell or use a one-off job:

```bash
python scripts/create_owner.py --email owner@yourdomain.com --password "<strong password>"
```

## 8. Verify

- `GET https://api.yourdomain.com/health` → `{"status":"healthy","database":"connected"}`
- Login from the frontend with the owner account
- Check Sentry dashboard receives a test event
- Check Railway logs for the startup banner — there should be no "PRODUCTION READINESS WARNINGS" block

## Built-in safety rails

The code will hard-fail on boot if any of these are true in production:

- `SECRET_KEY` is a dev default or shorter than 32 chars
- `ENCRYPTION_KEY` is a dev default
- `alembic upgrade head` fails

The code will log warnings (but start) if these are missing:

- `SENTRY_DSN` — no error visibility
- `SMTP_*` — emails silently fail
- `AWS_S3_BUCKET` — uploads fail
- `REDIS_URL` — rate limiting is per-instance only
- `CORS_ORIGINS` contains localhost — dev origins leaking into prod

## What's intentionally not done

- Frontend tests (101 failing) are not blocking deployment. They're written against an older UI contract.
- Backend coverage gate is 60% (below the 70% ideal). Low-coverage areas are payment/subscription services, which will be exercised manually during the first Stripe/Razorpay testing round.
- Token refresh requires page interaction (tokens are in-memory per HIPAA). Users who refresh the browser must log in again.
