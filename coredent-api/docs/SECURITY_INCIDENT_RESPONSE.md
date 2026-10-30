# Security Incident Response Plan
================================

**Owner:** Privacy/Security Officer
**Review frequency:** After every incident, plus quarterly
**Last reviewed:** 2026-06-02

This is the operational plan for responding to a security incident affecting CoreDent.  An "incident" is any actual or suspected event that compromises the confidentiality, integrity, or availability of ePHI, the production system, or the company's reputation.  This includes both confirmed breaches (which trigger HIPAA notification duties — see `HIPAA_COMPLIANCE_PROGRAM.md` § 5.2) and near-misses.

---

## 1. Severity classification

| Severity | Definition | Examples | First action |
|---|---|---|---|
| **SEV-1 (Critical)** | Active exploit in progress, or confirmed unauthorized access to production ePHI. | Sentry alert on a SQLi-shaped query, AWS KMS key revoked unexpectedly, customer reports seeing another customer's data. | Page on-call Security Officer within 15 min. |
| **SEV-2 (High)** | Suspected breach; investigation in progress; no evidence yet of ePHI access. | Failed login spike from a single IP, anomalous S3 access pattern, suspicious Sentry error pattern. | Notify on-call Security Officer within 1h. |
| **SEV-3 (Medium)** | Vulnerability disclosed, no exploitation observed. | New CVE in a dependency, bug-bounty report, internal pen-test finding. | Create ticket, schedule fix. |
| **SEV-4 (Low)** | Informational; documentation update, hardening task. | Outdated doc, missing label. | Backlog. |

---

## 2. Roles

- **Incident Commander (IC):** the Privacy/Security Officer. Owns the response end-to-end. Decides severity, declares "all clear".
- **Technical Lead:** the on-call senior engineer. Investigates, mitigates, restores.
- **Communications Lead:** the CTO. Owns external messaging (customers, press, regulators).
- **Scribe:** any team member not actively debugging. Maintains the incident log (`docs/incidents/active/INC-NNNN.md`).

The IC role is *single* — one person at a time. If the IC is unreachable, the CTO assumes the role.

---

## 3. Phases

### 3.1 Detection
Sources: Sentry alerts, S3 access logs, audit-log queries, customer reports, automated CI scans (pip-audit, bandit, OWASP ZAP), bug-bounty reports.

### 3.2 Triage (within 1h of detection for SEV-1, 4h for SEV-2)
- IC confirms the event is a real incident (not a false positive).
- IC classifies severity.
- IC creates `docs/incidents/active/INC-NNNN.md` with the basic facts.
- Scribe opens a dedicated Slack channel `#inc-NNNN`.
- IC assigns a Technical Lead.

### 3.3 Containment
Goals: stop the bleeding; preserve evidence.

Common actions:
- Disable compromised user accounts (`User.is_active = False`).
- Rotate secrets the attacker may have (`SECRET_KEY`, `ENCRYPTION_KEYS`, AWS keys, Stripe webhook secret, OAuth tokens).
- WAF rule to block the attack pattern (if applicable).
- Take affected systems offline if needed (e.g. read-only mode).
- Snapshot the DB and S3 for forensics; do NOT delete logs.

### 3.4 Eradication
- Patch the vulnerability that was exploited.
- Remove attacker persistence (backdoors, rogue IAM users, planted cron jobs).
- Verify with a second pen-test or by re-running the exploit attempt.

### 3.5 Recovery
- Restore from backup if data integrity is in question.
- Verify patient and billing data integrity.
- Re-enable user accounts.
- Resume normal operations.

### 3.6 Notification (HIPAA breach)
If the incident is a breach under HIPAA, follow `HIPAA_COMPLIANCE_PROGRAM.md` § 5.2. **Do not notify before the IC, CTO, and legal counsel have agreed on the wording.**

### 3.7 Post-incident review
Within 7 days, the IC leads a blameless review. The output is `docs/incidents/closed/INC-NNNN.md` containing:
- Timeline (detection → triage → containment → eradication → recovery → all-clear)
- Root cause
- Contributing factors
- What went well, what didn't
- Action items (with owners and deadlines)

Action items from post-incident reviews are tracked in the same ticket queue as feature work and *cannot be closed until verified done*.

---

## 4. Communication templates

### 4.1 Customer notification (initial, within 24-72h of confirmed breach)

```
Subject: [CoreDent] Important security notice

Dear [Customer Name],

We are writing to inform you of a security incident that may have
affected your data on [date]. We discovered the incident on [date]
and immediately engaged our security team.

What happened: [factual description, no jargon]
What information was involved: [scope]
What we are doing: [containment + remediation steps]
What you should do: [user-actionable items, e.g. reset password]

We are available to answer questions at [contact]. A more detailed
notice will follow within [X] days.

Sincerely,
[CTO name]
```

### 4.2 Internal status update (every 4h during SEV-1)

```
INC-NNNN status @ HH:MM
Severity: SEV-1
Status: [contained | investigating | mitigated | resolved]
Customer impact: [scope]
External comms: [pending | sent | N/A]
Next update: HH:MM
```

### 4.3 HHS breach notification (within 60 days, for ≥500 affected)

See https://ocrportal.hhs.gov/ocr/breach/wizard_breach.jsf for the online form. Required fields: covered entity name, business associate name (CoreDent), date of breach, date of discovery, type of breach, location of breached information, number of individuals affected, summary, mitigation steps.

---

## 5. Specific incident playbooks

### 5.1 Compromised staff account
1. `User.is_active = False` (via `POST /api/v1/staff/{id}` with role check or direct DB).
2. Invalidate all `UserSession` rows for the user.
3. Rotate `SECRET_KEY` (forces all tokens to expire) — but be aware this logs out every user globally.
4. Audit the user's recent API calls from the `AuditLog` table. Look for: data exports, role changes, deletion of audit logs, unusual IPs.
5. Notify the user out-of-band (call their known phone) and reset their password via support.
6. File a post-incident review.

### 5.2 SQL injection / data exfiltration
1. Enable WAF rule to block the exact payload (Cloudflare / Railway).
2. Identify the endpoint and the parameter.
3. Pull the `AuditLog` for the period to see which practice_ids were queried.
4. Pull the Sentry events for the period to see the full attack payload.
5. Hot-patch the endpoint or the ORM query.
6. Run the cross-tenant isolation test suite against the patched code.
7. File a breach determination; if ePHI was actually returned, treat as SEV-1.

### 5.3 Ransomware on production DB
1. Stop the API (returns 503 to all users).
2. Activate the "ransomware" scenario in `docs/BACKUP_DR_RUNBOOK.md`.
3. Spin up a new DB instance, restore the most recent known-good backup.
4. **Do not pay the ransom.** (Payment does not guarantee data return and funds future attacks.)
5. File a breach (yes, even a successful restore is a breach because the attacker had access during the window).
6. Notify customers + HHS within the HIPAA deadlines.

### 5.4 Lost device (employee laptop with no PHI)
1. Confirm via MDM that the disk is encrypted (FileVault / BitLocker).
2. Confirm the user did not sync CoreDent PHI to the device (we use the web app, no offline mode).
3. If both true: SEV-3 or SEV-4. Log and document. No external notification needed.
4. If either false: SEV-1. Engage the breach playbook.

---

## 6. Tools and access

- Sentry: production error tracking, alerting
- CloudWatch (or Railway metrics): DB / Redis / API metrics
- S3 access logs: every S3 request
- DB audit log: every API request via `AuditLog` table
- Slack `#incident-<n>`: real-time comms
- `docs/incidents/`: ticketed record

The Privacy/Security Officer and the Technical Lead have on-call rotation access to all of the above. The Scribe has read access only.

---

## 7. Drills

Quarterly, the Privacy/Security Officer runs a tabletop drill. Scenarios rotate through the four playbooks in § 5. The drill is timed and recorded. The post-drill review identifies process gaps and adds them to the backlog.
