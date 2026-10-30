# Production Status — CoreDent

**Last updated:** 2026-09-11

This is the single source of truth for CoreDent's production readiness. All other `.md` files in this repository that make readiness claims should be ignored. The detailed technical review is in `HONEST_PRODUCTION_REVIEW_2026.md`.

---

## TL;DR

| Area | Status |
|---|---|
| **Field-level PHI encryption** | ✅ Real (Fernet AAD-bound, multi-key support) |
| **PHI at-rest in DB** | ✅ Encrypted columns |
| **Multi-tenant isolation** | ✅ TenantGuard + per-endpoint scoping |
| **Cross-tenant isolation tested** | ✅ `tests/test_tenant_isolation.py` |
| **PHI at-rest proven by test** | ✅ `tests/test_phi_encrypted_at_rest.py` |
| **Auth** | ✅ bcrypt 14, JWT HS256 (PyJWT), lockout, hashed refresh, anti-enum |
| **Stripe / webhooks** | ✅ Re-implemented HMAC verifier, fail-closed |
| **Production config validation** | ✅ Hard fail-closed in `ENVIRONMENT=production` — 13 config-check groups incl. placeholder detection (`SECRET_KEY`, `ENCRYPTION_KEYS`, `SEARCH_INDEX_KEY`, `KMS_BACKEND`/`AWS_KMS_KEY_ARN`, `SENTRY_DSN`, `STRIPE_WEBHOOK_SECRET`, `REDIS_URL`, `TRUSTED_PROXIES`, `MONITORING_TOKEN`, SMTP, `AWS_S3_BUCKET`, `ALLOWED_HOSTS`, `CORS_ORIGINS`) |
| **Backup / DR** | ✅ 540-line runbook, RPO 1h / RTO 4h, monthly test |
| **Observability** | ✅ Sentry required-in-prod, JSON logs, security event middleware |
| **CORS / CSP / headers** | ✅ Strict CSP (no `unsafe-inline`), HSTS, X-Frame-Options |
| **CI** | ✅ pip-audit + npm audit, unit/integration suites, schema drift, Postgres parity |
| **Dependency hygiene** | ✅ `cryptography` 44.x, PyJWT, direct bcrypt, `pip-audit` |
| **Billing race conditions** | ✅ Postgres advisory lock + `SELECT FOR UPDATE` |
| **Plan quota enforcement** | ✅ `enforce_plan_quota()` dependency gates patient/staff creation against the plan's `limits` map (added 2026-08) |
| **Accepted payment methods** | ✅ `POST /billing/payments/` rejects methods outside the practice's configured `acceptedPaymentMethods` |
| **Real-PostgreSQL concurrency tests** | ✅ `tests/test_postgres_concurrency.py` — invoice-number + double-payment races; runs on CI Postgres, skips on SQLite |
| **Uvicorn proxy headers** | ✅ `--proxy-headers` + `TRUSTED_PROXIES` env |
| **Service worker PHI caching** | ✅ NetworkOnly for `/api/*` (verified) |
| **DemoBanner in prod bundle** | ✅ Build-time no-op via `import.meta.env.PROD` |
| **Email failure handling** | ✅ `_log_email_failure()` → Sentry |
| **Durable email queue** | ✅ Celery task with exponential-backoff retry (5 attempts, ~13h window) |
| **Per-user rate limits** | ✅ Redis-backed `user_rate_limit("30/minute")` decorator |
| **KMS integration** | ✅ Pluggable KmsClient (env / AWS KMS / local) — switch via `KMS_BACKEND=aws` |
| **HIPAA compliance program** | ✅ `docs/HIPAA_COMPLIANCE_PROGRAM.md` (8 sections, full 45 CFR coverage) |
| **Security incident response** | ✅ `docs/SECURITY_INCIDENT_RESPONSE.md` (severity matrix, 4 playbooks, comms templates) |
| **Pen-test scope** | ✅ `docs/PENTEST_SCOPE.md` (2-week black/grey-box, candidate firms, budget) |
| **Public security policy** | ✅ `SECURITY.md` at repo root (vuln disclosure + safe harbor) |
| **Frontend token storage** | ✅ In-memory + sessionStorage, no localStorage |
| **Documentation** | ✅ Consolidated to this file + `HONEST_PRODUCTION_REVIEW_2026.md` |
| **Patient erasure (GDPR art. 17) flow** | ✅ `POST /patients/{id}/anonymize` scrubs PHI + search HMACs + portal access, cancels future appts, audits `patient_anonymized`; UI = "GDPR Erase" type-to-confirm dialog |
| **Patient export (portability)** | ✅ `GET /patients/{id}/export` full-record JSON download |
| **Refund workflow** | ✅ Gateway-first Stripe & Razorpay refunds via `POST /billing/payments/{id}/refund` (partial+full, row-locked, ledger-consistent) + `RefundPaymentDialog` UI + `payment_refunded` automation event |
| **Platform console (SaaS ops)** | ✅ `/platform/*` metrics, clinics (+suspend/reactivate), users (+deactivate/reactivate w/ locks), subscriptions, audit feed |
| **Reports aggregations** | ✅ `byMonth`/`byProcedure`/`treatmentAcceptance.byMonth`/`peakHours`/`byChair`/`byDayOfWeek` filled (tz-aware), no more empty chart stubs |
| **Accountant role** | ✅ `UserRole.ACCOUNTANT`, billing/reports server-side + routes/sidebar |
| **Per-practice retention override + jurisdiction presets** | ✅ `practices.retention_years`/`jurisdiction` (migrations b5e2f7a9c4d1/e9f1a4b3d0c6); purge takes max(practice, platform floor); Settings jurisdiction dropdown auto-fills suggested years + minor-rule guidance (`src/lib/retentionPresets.ts`, 50 states + DC + 5 countries) |
| **Data Retention Policy & Purge** | ✅ Full purge pipeline implemented (`purge_retention_records` daily Celery job, cascading cleanup across notes/charts/orders/codes) + policy template |
| **Backup / DR drill checklist** | 🟡 `scripts/backup-dr-drill-checklist.md` + `scripts/backup-dr-drill.ps1` runner — drill must be *executed* monthly |
| **Live-integration smoke** | 🟡 `scripts/live-integration-smoke.ps1` + `scripts/gate-production.ps1` — requires staging creds to execute fully |
| **Legal pages (public)** | ✅ `/legal/{privacy,terms,dpa,security,refunds,contact}` implemented + linked |

---

## Verdict

**NO-GO** for any environment with real patient data or payment processing. Online payments are intentionally fail-closed (HTTP 503) until transactional persistence, idempotent reconciliation, and webhook reliability are implemented and validated. The four fake dashboards are fixed, making the SaaS more honest and beta-ready, but it is **NO** yet for the open market as a complete dental platform. It is not ready for:
- US healthcare customers where the vendor is the Business Associate
- Open sign-up from the public internet
- Any environment with real ePHI liability and a signed vendor BAA

---

## What was changed in this update (2026-06-02)

### Pass 1 (P1 + P2 from the prior review)
1. Dependency CVEs — bumped `cryptography` 42→44, migrated to `PyJWT` and direct `bcrypt` (dropped unmaintained `python-jose` and `passlib`).
2. Cross-tenant isolation test suite — new `tests/test_tenant_isolation.py`.
3. PHI encryption-at-rest test — new `tests/test_phi_encrypted_at_rest.py`.
4. Billing race conditions — advisory lock for invoice numbers, `SELECT FOR UPDATE` for payment→status.
5. Uvicorn proxy headers — `proxy_headers=True` + `TRUSTED_PROXIES` env.
6. CSP — removed `'unsafe-inline'` from `script-src` and `style-src`.
7. Email failure handling — `_log_email_failure()` reports to Sentry.
8. DemoBanner — build-time no-op in production.
9. `@sentry/browser` v7→v8.
10. CI — added `pip-audit --strict` step.
11. Documentation — this file replaces 20+ contradictory `.md` files.

### Pass 2 (the previously-pending items)
12. **Durable email queue** — new `app/core/email_tasks.py` with Celery `send_email_task` (exponential backoff 1m→5m→25m→2h→10h, max 5 retries, `event_type=email_permanent_failure` Sentry alert). Applied to registration and password-reset emails.
13. **Per-user rate limits** — new `app/core/rate_limit.py` with Redis-backed `user_rate_limit("30/minute")` decorator. Fails OPEN if Redis is down. Layered on top of the existing IP-based slowapi. Applied to `GET /patients`.
14. **KMS integration** — new `app/core/kms.py` with `KmsClient` interface and three backends (`env`, `aws`, `local`). Set `KMS_BACKEND=aws` + `AWS_KMS_KEY_ARN` + the data-key blob in `ENCRYPTION_KEYS` to switch to AWS KMS with the data-key pattern.
15. **HIPAA compliance program** — new `docs/HIPAA_COMPLIANCE_PROGRAM.md` covering all 8 administrative safeguards (SRA, workforce security, access management, training, incident procedures, contingency, evaluation, BAAs) with quarterly review cadence and a vendor BAA tracker.
16. **Security incident response plan** — new `docs/SECURITY_INCIDENT_RESPONSE.md` with severity matrix, 4 incident playbooks (compromised account, SQLi, ransomware, lost device), and breach-notification templates.
17. **Pen-test scope** — new `docs/PENTEST_SCOPE.md` with 2-week black/grey-box RFP, OWASP WSTG+ASVS Level 2 methodology, deliverable spec, budget, candidate firms.
18. **Public security policy** — new `SECURITY.md` at the repo root for vulnerability disclosure + safe harbor.
19. **CI gates** — the workflow runs six jobs: backend migrate/audit/lint/test, backend dependency audit, backend model/migration schema drift, frontend audit+typecheck+lint+coverage+build, frontend dependency audit, and a nightly full backend suite. `tests/test_tenant_isolation.py` and `tests/test_phi_encrypted_at_rest.py` run inside the backend gate step rather than as separate jobs.

    **There is no OWASP ZAP step.** An earlier revision of this document claimed one had been added to CI; it never was. Automated dynamic scanning remains outstanding and is covered by the contracted penetration test scoped in `docs/PENTEST_SCOPE.md`.

---

## Operational checklist before closed beta

- [ ] `pip install -r requirements.txt` resolves cleanly with the new pins.
- [ ] `pytest tests/test_tenant_isolation.py tests/test_phi_encrypted_at_rest.py` passes on staging Postgres.
- [ ] `start.py` is the new entry point (it now sets `proxy_headers=True`).
- [ ] All fail-closed production config checks pass (13 groups — boot fails loudly listing any missing/placeholder value, see `docs/PRODUCTION_REQUIRED_ENV.md`): `SECRET_KEY`, `ENCRYPTION_KEYS`, `SEARCH_INDEX_KEY`, `KMS_BACKEND` (+ `AWS_KMS_KEY_ARN` and an `aws:` data-key entry when `KMS_BACKEND=aws`), `SENTRY_DSN`, `STRIPE_WEBHOOK_SECRET`, `REDIS_URL`, `TRUSTED_PROXIES`, `MONITORING_TOKEN`, `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`, `AWS_S3_BUCKET`, `ALLOWED_HOSTS`, `CORS_ORIGINS`.
- [ ] Celery worker is running: `celery -A app.core.celery_app worker -Q default,communications,reminders,emails -l info` (the new `emails` queue is for `email_tasks`).
- [ ] BAAs signed with: Railway, Sentry, Stripe, Twilio, AWS.
- [ ] Healthcare-attorney-reviewed privacy policy.
- [ ] 5–10 friendly practices onboarded manually; their feedback drives the open-beta decision.
- [ ] First pen-test engagement scoped and contracted (see `docs/PENTEST_SCOPE.md`).
- [ ] First SRA commissioned (see `docs/HIPAA_COMPLIANCE_PROGRAM.md` § 1).

---

## What is still NOT done (for the open market)

These require external human work, external systems integration, or broader product and operational work that is not yet implemented:

### Missing Integrations & Broader Product Features
- **DICOM/TWAIN Capture & AI Imaging**: Imaging hub supports basic API-backed upload and viewing, but direct DICOM/TWAIN workstation capture and AI-driven imaging interpretation are not connected.
- **Real Insurance Clearinghouse (DentalXChange/ERA/Denial workflows)**: Real clearinghouse connections, electronic remittance advice (ERA) flows, and automated denial management are stubs/mocks.
- **Live Infrastructure/Staging Validation**: Verification with live staging accounts is still pending for Stripe, SMTP, Twilio/SendGrid, S3, Redis, and Celery.
- **Dentrix/Open Dental Migration Tools**: Automated migration utilities to ingest patient databases from legacy systems like Dentrix and Open Dental are not built.
- **E-Prescribing & Advanced Intake Forms**: Integrated e-prescribing and dynamic consent/intake form builders are missing.
- **True Multi-Location/DSO Data Model**: The tenancy model limits database operations to single isolated practices; multi-location consolidation (DSO view) is not supported.

### Legal, Administrative, & Security Programs (Operational Compliance)
- **Vendor BAAs**: **Not in place.** BAAs still need to be signed with Railway, Sentry, Stripe, Twilio, and AWS — see the unchecked item in the pre-beta checklist above. An earlier revision of this document claimed these were completed; they are not, and this is the blocking item for handling real ePHI.
- **Healthcare-Attorney Review**: Privacy policy, terms of service, and clinical consent workflows need specialized attorney sign-off.
- **SRA, Training, & Testing**: A formal Security Risk Assessment (SRA), workforce security training, professional penetration testing, and disaster-recovery/business-continuity exercises are still outstanding.

Everything else (code, tests, configuration, documentation) is now in place for a defensible closed beta.

---

## Verified locally (last full backend rerun: 2026-09-11)

- Phase-1/2 targeted suites: **119 tests green** — production-gaps (16), patients (14),
  reports (6 total incl. comprehensive), billing (38), retention-purge (6), plus
  payments/payment-service/payment-methods/enterprise/auth regression. Full-suite
  totals: 760+ backend / 1,031 frontend previously recorded.
- Scheduled hard purge (`purge_expired_anonymized_patients`): 6 new retention tests
  green (eligibility math, full async purge w/ billing history, recent-anonymize
  exclusion, async shape, batch-scan path with Fernet-marker matching).
- Backend: Alembic migration chain renders offline + upgrades fresh SQLite; real-PostgreSQL
  migration/concurrency runs in CI (`postgres:16-alpine`).
- Frontend: `npm run typecheck` (both tsconfigs) 0 errors; ESLint `--max-warnings 0` clean.
- `npm audit --audit-level=moderate`: no vulnerabilities. `pip-audit --strict`: clean.
- Production gate: `pwsh scripts/gate-production.ps1 [--with-integrations] [--drill latest.dump]`
  is the one-shot readiness check; DR drill + live-integration smoke are SKIP-friendly until
  real staging credentials are supplied.

Docker is not installed in the review workstation, so the container topology still requires
a staging runtime smoke test before deployment. External BAAs, legal review, live integration
credentials, an SRA, and a professional penetration test remain non-code launch requirements.
