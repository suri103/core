# Production Required Environment Variables

The API **fails closed at import time**. If a required setting is missing, empty,
a known-bad default, or a template placeholder, the process refuses to start
rather than running insecurely.

- Enforcement lives in `coredent-api/app/core/config_simple.py` (the
  `if self.ENVIRONMENT not in _LOCAL_ENVIRONMENTS:` block near the end).
- Referenced from `PRODUCTION_STATUS.md` § "Operational checklist before closed beta".

## Which environments this applies to

Only these are exempt:

```
development, dev, test, testing, local
```

**Everything else is gated** — `staging`, `uat`, `preview`, `production`, and
even a typo like `prod`. There is no partial-trust environment. A staging deploy
must be as complete as production.

## Placeholder detection

A value fails if it contains any of these substrings (case-insensitive):

```
change_this   change_me   change-me   changeme
your-         your_       yourdomain  yoursite   your_site
example.com   todo        tbd
```

Note `example.com` and `yourdomain` are in that list, so copying a template line
verbatim always fails. Empty strings are *not* treated as placeholders — they are
caught separately by explicit `not <VAR>` checks, with two exceptions noted below.

This token list is applied to `SECRET_KEY`, `ENCRYPTION_KEY`/`ENCRYPTION_KEYS`,
`SEARCH_INDEX_KEY`, `STRIPE_WEBHOOK_SECRET`, `MONITORING_TOKEN`, `SMTP_HOST`,
`SMTP_USER`, `SMTP_PASSWORD`, `AWS_S3_BUCKET`, and each entry of
`ALLOWED_HOSTS` / `CORS_ORIGINS`.

`SENTRY_DSN` is the exception: it has its own narrower check, which only rejects
a literal `your-sentry-dsn` or the exact values `changeme` / `todo` / `tbd`.

## Required checks

`PRODUCTION_STATUS.md` tracks these as "13 groups". The table below lists those
13 plus `DATABASE_URL`, which is validated by the same block.

| Variable | Requirement | How to get it | If it fails |
|---|---|---|---|
| `DATABASE_URL` | Must **not** start with `sqlite` | Railway `${{Postgres.DATABASE_URL}}` | `FOR UPDATE` / advisory locks silently degrade to check-then-insert — double-payment and double-booking guards stop working |
| `SECRET_KEY` | Env set, ≥32 chars, not a bad default or placeholder | `python ../generate_secret_key.py` (repo root) | JWT forgery |
| `ENCRYPTION_KEYS` | Non-placeholder (or legacy `ENCRYPTION_KEY`) | see below | PHI cannot be encrypted/decrypted |
| `SEARCH_INDEX_KEY` | ≥32 chars, non-placeholder, **independent** of `ENCRYPTION_KEYS` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | Search indexes are HMACs over sensitive values; deriving from a public Fernet key ID makes them predictable to anyone who steals the DB |
| `KMS_BACKEND` | One of `env`, `aws`, `local` | `env` to start | Bad value crashes at boot; with `aws`, `AWS_KMS_KEY_ARN` **and** an `aws:<blob>` entry in `ENCRYPTION_KEYS` are also required. The error message cites `scripts/generate_aws_data_key.py`, which does **not exist** in the repo — creating that key blob is currently an undocumented manual step. |
| `SENTRY_DSN` | Non-empty, not `your-sentry-dsn`/`changeme`/`todo`/`tbd` | Sentry project settings | No error visibility in production |
| `STRIPE_WEBHOOK_SECRET` | Non-empty, non-placeholder | Stripe → Webhooks → endpoint signing secret | Webhooks are unverified and payment events are refused |
| `REDIS_URL` | Non-empty | Railway `${{Redis.REDIS_URL}}` | In-process rate limiter does not work across replicas |
| `TRUSTED_PROXIES` | Non-empty, not `*`, every entry a valid IP/CIDR | Railway edge CIDR | `X-Forwarded-For` spoofing evades per-IP rate limits and poisons the HIPAA audit log's IP column |
| `MONITORING_TOKEN` | ≥32 chars, non-placeholder | `python -c "import secrets; print(secrets.token_hex(32))"` | `/metrics` is world-readable |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | Host ≠ `localhost` and non-placeholder; user non-empty and non-placeholder; password non-placeholder | Mailtrap, SendGrid, SES, Postmark | Password resets, verification, and reminders fail |
| `AWS_S3_BUCKET` | Non-empty, non-placeholder | AWS S3 | File and image uploads fail |
| `ALLOWED_HOSTS` | Not the dev default (`localhost,127.0.0.1`), no placeholders | your API domain(s), plus `healthcheck.railway.app` | Host header attacks |
| `CORS_ORIGINS` | No `localhost`, no placeholder, no `*` | exact frontend origin(s) | Browser blocks all API calls |

### Generating the crypto values

```bash
# SECRET_KEY (also: python generate_secret_key.py)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# ENCRYPTION_KEYS - note the current: prefix, and generate a SEPARATE one
# for SEARCH_INDEX_KEY (never reuse)
python -c "from cryptography.fernet import Fernet; print('current:' + Fernet.generate_key().decode())"

# SEARCH_INDEX_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"

# MONITORING_TOKEN
python -c "import secrets; print(secrets.token_hex(32))"
```

**Key rotation:** `ENCRYPTION_KEYS` accepts a comma-separated keyring
(`current:<new>,previous:<old>`). Rotating after PHI exists requires
re-encrypting stored data, so generate unique keys per environment and never
reuse between staging and production.

## Variables the gate does NOT check but that still break things

These boot cleanly and fail later — they are the most expensive class of
misconfiguration because the deploy looks successful.

| Variable | Default when unset | Consequence |
|---|---|---|
| `EMAIL_PROVIDER` | `console` for **any** environment except `production` | **Highest-impact trap.** Staging/uat/preview boot green, password reset returns success, and the email is only printed to the logs. Must be set to `smtp` explicitly outside production. |
| `SMS_PROVIDER` | `console` for any environment except `production` | Same, for SMS |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | empty | Gate only requires `STRIPE_WEBHOOK_SECRET`; payments fail at runtime |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | empty | Boots, fails on first upload (unless an IAM role is attached) |
| `SMTP_PASSWORD` | empty | An empty password is **not** a placeholder, so setting `SMTP_USER` with a blank password passes the gate and then fails SMTP auth at runtime |
| `SMTP_FROM` | `noreply@coredent.com` | Never validated — a `yourdomain.com` sender passes the gate. Must be a verified sender before production. |
| `CLAMAV_HOST` | unset | ClamAV init fails, falls through to VirusTotal, which is also unconfigured, and that path **fails open** — uploads are stored unscanned |
| `USAGE_TRACKING_ENABLED` | `false` | Metering off: `Subscription.current_usage` stays 0 and usage-based invoices bill nothing |
| `DEBUG` | `false` outside local | Not validated, but `DEBUG=True` silently **disables `TrustedHostMiddleware`** (see `app/main.py`), removing Host-header protection |

## Per-service matrix

Same image, three roles selected by `PROCESS_TYPE` (see `start.py`).

| Setting | `api` (web) | `worker` | `beat` |
|---|---|---|---|
| `PROCESS_TYPE` | `web` | `worker` | `beat` |
| `RUN_MIGRATIONS_ON_START` | `true` | `false` | `false` |
| Public domain | yes | no | no |
| Replicas | 1+ | 1+ | **exactly 1** |

- Workers must never run DDL; only the web/release role migrates.
- Two `beat` replicas double-fire every scheduled task.
- All three must share identical `ENCRYPTION_KEYS`, `SEARCH_INDEX_KEY`, and
  Postgres/Redis — a worker that cannot decrypt PHI corrupts data on write.

## Verifying without deploying

**Full fail-closed suite** — asserts a correctly-provisioned env imports cleanly,
then mutates each required value to a bad one and asserts the import is refused.
This is the authoritative check and it passes today (12/12 mutations refused):

```bash
cd coredent-api
python scripts/phase3_config_dryrun.py
```

**Check a single env file.** The gate runs on **import** of `config_simple.py`,
so any import of the app exercises it:

```bash
cd coredent-api
python -c "from app.core.config_simple import settings; print('ok', settings.ENVIRONMENT)"
```

A failure prints every offending variable at once:

```
Refusing to start: environment 'staging' is not a local/dev environment and
requires production-grade configuration (local/dev/test environments are exempt):
  - SECRET_KEY is missing or uses a known-bad default ...
  - ...
```

Note: `${{Postgres.DATABASE_URL}}`-style Railway references cannot resolve
outside Railway — supply a real URL when testing locally.

## Related

- `docs/RAILWAY_DEPLOY_STEPS.md` — end-to-end Railway + Vercel runbook
- `coredent-api/.env.staging.railway` — staging variable template
- `coredent-api/.env.production.example` — production variable template
- `scripts/gate-production.ps1`, `scripts/production-smoke.ps1`
