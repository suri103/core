# CoreDent — Data Retention & Deletion Policy

**Owner:** Platform team (proposed) · **Version:** 0.1 · **Status:** DRAFT — requires healthcare-attorney review before production use

This policy governs how long CoreDent retains: (a) data we process on behalf of a Practice,
(b) data about Practice users, and (c) operational/security data we generate ourselves.
It aligns with HIPAA's 6-year documentation minimum (45 CFR 164.316(b)), the GDPR/DPDP
right-to-erasure expectations, and the dental record-retention norms used by the major
dental SaaS vendors (7-year adult / majority+5-7yr minor safe harbor). Where a Practice's
jurisdiction (state/provincial/other) sets a longer minimum, the longer period applies.

> ⚠️ This document is policy template, not legal advice. Retention *minimums* vary by US
> state dental board (commonly 5-7 years for adults; 5-7 years after majority for minors),
> and by jurisdiction. Have counsel confirm the table against the jurisdictions you sell into.

---

## 1. Retention categories and default windows

| # | Category | Example records | Default retention | Basis / rationale |
|---|----------|-----------------|-------------------|-------------------|
| R1 | **Patient clinical records** (encrypted PHI) | name, DOB, contact, medical/dental history, chart, notes, imaging, treatment plans | **7 years** after last treatment (or **age of majority (18/21) + 7 years** for minors, whichever is later) | State dental-board safe harbor 🇺🇸; GDPR art. 5(1)(e) storage limitation (configurable per practice) |
| R2 | **Billing / payments / claims** | invoices, payments, refunds, claims, ERA, payment plans | **7 years** from final payment/claim disposition (statute of limitations + 3-yr IRS/audit common minimum) | Limitation periods + insurance audit windows |
| R3 | **Insurance eligibility / pre-auth** | eligibility checks, pre-authorizations | 7 years from service date | Match claims window |
| R4 | **Communications / messages** | email/SMS/portal messages, reminders | 2 years (configurable; not PHI-bearing beyond the identifiers needed to deliver) | Utility vs. privacy |
| R5 | **Staff / accounts** | user rows, invitations, role changes, sessions | Account lifetime + **60 days** after termination | Operational; terminated users are deactivated immediately (login blocked) |
| R6 | **Audit logs** (write-once) | `audit_logs`, security events | **7 years** (≥ HIPAA 6-yr doc minimum) | HIPAA § 164.316(b)(2); incident forensics |
| R7 | **Sessions & tokens** | refresh sessions, portal sessions, revoked tokens | Active until expiry; **purged 30 days** after expiry/revocation | Least-access |
| R8 | **Backups** | full DB dumps, WAL | Rolling: keep **35 daily / 12 weekly / 12 monthly** (≈1 yr), then destroy | DR window vs. storage-limitation; see §4 |
| R9 | **Stripe/SaaS platform subscription data** | plans, subscriptions, dunning, usage | Practice subscription lifetime + **7 years** after closure (financial) | Books/financial records |

## 2. Erasure & right-to-delete (GDPR art. 17 / DPDP)

CoreDent implements a **two-tier** deletion model because a plain `DELETE` of patient rows is
blocked by custodial references (invoices, claims, payment plans) that law requires us to keep:

1. **Anonymization (implemented — `POST /patients/{id}/anonymize`)** — the standard erasure
   action. Every PHI column is scrubbed in place, **including search indexes (HMACs) and
   portal access**; future appointments are cancelled; the row becomes an anonymous,
   non-resolvable placeholder so billing/claim references remain valid. Audited as
   `patient_anonymized`.
2. **Hard purge (implemented — scheduled daily in Celery beat)** — a platform maintenance
   job (`purge_retention_records` running daily at 05:00 UTC) that, after the R2 claims window
   has elapsed (7 years post-disposition or practice retention override) for an anonymized
   patient, hard-purges patient data with full cascading cleanup across notes, charts,
   referrals, lab orders, communications, and portal access codes, recording an immutable
   audit record.

Practices may also request **full account closure** (see §3); users may request erasure of
their own account data (deactivated at removal + 60-day window per R5).

## 3. Cancellation / closure / export

- While a subscription is active, CoreDent does not delete Practice data.
- On cancellation: access continues until period end. The Practice may **export** a complete
  patient dataset (`GET /patients/{id}/export`, GDPR portability) at any time.
- After closure, data is retained per the windows above, then destroyed. The owner may request
  a **certificate of destruction** (deliverable for the platform team once the hard-purge job
  and destruction-logging land).
## 4. Backups (see also `scripts/backup-dr-drill-checklist.md`)

- Backups are **encrypted** (consistent with field-level PHI encryption) and stored **offsite**.
- Targets: **RPO ≤ 1 h** (continuous WAL) and **RTO ≤ 4 h**, tested **monthly** via restore drill.
- Retention per R8; backups older than ~1 year are destroyed — they are a DR tool, not an
  archive for the records themselves (an archive that long would conflict with storage
  limitation).

## 5. Enforcing retention in code (existing vs. TODO)

| Action | Status |
|--------|--------|
| `POST /patients/{id}/anonymize` (PHI scrub + index scrub + portal revoke + audit) | ✅ Implemented |
| `GET /patients/{id}/export` (portability) | ✅ Implemented |
| Deactivate disabled users at termination (login already blocks `is_active=False`) | ✅ Implemented |
| Audit-log write-once + do-not-delete DB triggers | ✅ Implemented |
| Celery purge job: `portal_lockout`, `revoked_token`, `patient_portal_sessions` expiry sweep | ✅ Implemented (see models) |
| Celery purge job: anonymized-row hard delete after R2 window | ✅ Implemented (`app.core.tasks.purge_expired_anonymized_patients`, daily beat, 7-year default window, write-once `patient_purged` audit = certificate of destruction) |
| Destruction-log / certificate-of-destruction | ❌ TODO |
| Retention-region config per practice (state/jurisdiction override) | ✅ Implemented: `practices.retention_years` + `practices.jurisdiction` (migration b5e2f7a9c4d1 + e9f1a4b3d0c6); Settings UI with a jurisdiction preset picker (`src/lib/retentionPresets.ts` — 50 states + DC + 5 countries, adult/minor guidance, platform-floor guarantee); purge takes max(practice, platform floor) so retention can only extend |

## 6. Review & sign-off

- [ ] Healthcare attorney review (US state variations + target international markets)
- [ ] Confirm 7-year windows against each state/country you sell into
- [x] Set the R2 hard-purge schedule in the Celery beat + implement the job (scheduled daily at 05:00 UTC)
- [ ] Publish a customer-facing summary (what we keep, how long, how to erase)