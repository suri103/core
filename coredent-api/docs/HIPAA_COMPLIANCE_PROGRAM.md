# CoreDent — HIPAA Compliance Program

**Owner:** CTO + designated Privacy/Security Officer
**Review frequency:** Quarterly
**Last reviewed:** 2026-06-02

This document is the operational HIPAA program for CoreDent. It is **not** a marketing artifact. The technical controls in this codebase (encryption, tenant isolation, audit log, webhook verification) are necessary but not sufficient for HIPAA compliance — HIPAA is an operational program built on policies, training, vendor management, and incident response. This document is the program's operating manual.

---

## 1. Security Risk Assessment (SRA) — 45 CFR § 164.308(a)(1)(ii)(A)

A written, reviewed, and updated assessment of potential risks to ePHI is required annually. The SRA covers:

- Threats: ransomware, insider misuse, supply-chain compromise, credential theft, social engineering
- Vulnerabilities: missing patches, weak authentication, misconfigured S3 buckets, log shipping of PHI
- Likelihood and impact ratings
- Mitigations (mapped to the controls in this codebase and in this document)

**Action item:** Engage a healthcare-IT consultant to perform the first SRA within 30 days of closed-beta launch. The consultant's deliverable is a 30+ page report that the CTO reviews and signs.

---

## 2. Workforce Security — 45 CFR § 164.308(a)(3)

### 2.1 Authorization or supervision
- All CoreDent engineers with production data access must (a) pass a background check, (b) sign a confidentiality agreement, and (c) be listed in `docs/team/roster.csv` with their access scope.
- Production DB access is granted per-engineer, logged, and revoked on termination. Use `infra/scripts/grant_db_access.sh` and `revoke_db_access.sh`.

### 2.2 Workforce clearance
- New hires are added to the roster by HR on start date; engineering manager reviews at week 1.
- Terminations are processed by HR within 1 business day: roster removed, DB access revoked, SSO disabled, Sentry/GitHub removed from org.

### 2.3 Termination procedures
- Termination checklist (in `docs/team/termination_checklist.md`): revoke SSH keys, rotate shared secrets the person had access to, audit their recent admin actions via the `AuditLog` table.

### 2.4 Workforce training — REQUIRED EVERY NEW HIRE AND ANNUALLY
- All engineers and customer-facing staff complete a 1-hour HIPAA awareness training within 30 days of hire. Topics: what is PHI, what is ePHI, the minimum-necessary rule, the breach-notification rule, and the criminal penalties for willful violation (up to $250k / 10 years per offense).
- Engineers who work on the codebase also complete a 2-hour secure-coding training covering: OWASP Top 10, secret management, encryption, SQL injection, XSS, CSRF, dependency CVEs, and the company's specific secure-coding standards.
- Training records: `docs/team/training_records.csv` (signed by the trainee, countersigned by the manager).

---

## 3. Information Access Management — 45 CFR § 164.308(a)(4)

### 3.1 Access authorization
- The `UserRole` enum (`OWNER`, `ADMIN`, `DENTIST`, `HYGIENIST`, `FRONT_DESK`, `STAFF`) is the only role system. No ad-hoc roles. The `require_role(*roles)` dependency in `app/api/deps.py` is the only role gate.
- Cross-tenant access is technically prevented by the `TenantGuardMiddleware` AND by the per-endpoint `WHERE practice_id = :practice_id` clause. Both must be present.

### 3.2 Access establishment and modification
- New staff accounts are created by `OWNER` or `ADMIN` via `POST /api/v1/staff/`. The endpoint validates password strength (`validate_password_strength` in `app/core/security.py`).
- Role changes: only `OWNER` can change a user's role (`PUT /api/v1/staff/{user_id}` enforces this).
- Inactivation: `OWNER`/`ADMIN` can inactivate; only `OWNER` can inactivate another `OWNER` (`staff.py:inactivate_staff`).
- All of the above is recorded in the `AuditLog` table with `event_type` = `staff_created`, `staff_updated`, `staff_inactivated`.

### 3.3 Access review — REQUIRED QUARTERLY
- Run `python scripts/access_review.py` which lists every user in the system, their role, last login, and the date they were created.
- The Privacy/Security Officer reviews the list and flags any user that should not have access. The script writes a signed PDF to `docs/access_reviews/YYYY-QN.pdf` and emails it to the CTO.

---

## 4. Security Awareness and Training — 45 CFR § 164.308(a)(5)

- Quarterly phishing simulation (KnowBe4 or similar). Anyone who clicks a simulated phishing link must re-take the awareness training.
- Annual tabletop incident-response exercise (see § 10).

---

## 5. Security Incident Procedures — 45 CFR § 164.308(a)(6)

### 5.1 Incident response plan
See `docs/SECURITY_INCIDENT_RESPONSE.md` (companion document). The plan covers:
- Detection sources (Sentry alerts, S3 access logs, audit log queries, customer reports)
- Triage and severity classification
- Containment, eradication, recovery
- Notification (HHS, customers, affected individuals, media)
- Post-incident review

### 5.2 Breach notification — 45 CFR § 164.404, § 164.406, § 164.408
- A "breach" is any unauthorized acquisition, access, use, or disclosure of unsecured PHI that compromises privacy or security.
- **Notification deadlines:** affected individuals within 60 days; HHS within 60 days for ≥500 individuals or immediately for breaches affecting >500. Media notification within 60 days for breaches affecting >500 in a state.
- The Privacy/Security Officer is the single point of contact for breach determination. The CTO signs off on all external notifications. Legal counsel is consulted before any public statement.
- All breaches are recorded in `docs/breaches/incidents.csv` with: date detected, date contained, scope (number of individuals), root cause, remediation, notification status.

---

## 6. Contingency Plan — 45 CFR § 164.308(a)(7)

- **Data backup:** see `docs/BACKUP_DR_RUNBOOK.md`. Hourly `pg_dump` to S3, daily S3 cross-region replication, RPO 1h, RTO 4h.
- **Disaster recovery:** the backup runbook contains four recovery scenarios (DB corruption, full infra failure, ransomware, key compromise) with step-by-step procedures and time estimates.
- **Emergency mode operations:** the runbook has a "degraded operations" section: if the DB is read-only, the app serves a banner; if the DB is fully unavailable, the app returns 503 with a clear message.
- **Testing and revision:** monthly DR test (restore a backup to a scratch environment, verify it boots and serves data), quarterly full DR drill (rotate through the four scenarios).
- **Applications and data criticality analysis:** maintained as a spreadsheet in `docs/criticality_analysis.xlsx`. Re-reviewed quarterly.

---

## 7. Evaluation — 45 CFR § 164.308(a)(8)

- Annual technical evaluation of the security program. The first evaluation is performed by an external auditor 12 months after first BAA is signed. Subsequent evaluations are annual.
- Quarterly internal evaluation using the SRA + this document + the access review report as inputs.
- The Privacy/Security Officer maintains an evaluation log in `docs/evaluations/`.

---

## 8. Business Associate Agreements (BAAs) — 45 CFR § 164.502(e), § 164.504(e)

A BAA is a written contract between CoreDent and any vendor that creates, receives, maintains, or transmits PHI on our behalf. **No vendor with PHI access is used without a signed BAA in place.**

| Vendor | Access | BAA Status | Contact | Renewal Date |
|---|---|---|---|---|
| Railway (hosting) | All data | Signed 2026-04-01 | support@railway.app |