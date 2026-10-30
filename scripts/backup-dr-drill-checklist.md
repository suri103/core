# CoreDent — Backup / Disaster-Recovery Drill (checklist + runbook)

**Cadence:** monthly (first Tuesday, non-patient-hours) + after any schema-affecting release.
**Targets:** RPO ≤ 1 h · RTO ≤ 4 h · backup retention 35d/12w/12m (§ R8 of
`docs/DATA_RETENTION_POLICY.md`).

> This is the *checklist*. The companion runner `scripts/backup-dr-drill.ps1` automates the
> mechanical steps and measures RTO; the human steps below (documented evidence, sign-off,
> restore-detect verification) are what make a drill a *drill* instead of a script.

---

## A. Preconditions (done the day before)

- [ ] A1. Confirm snapshot storage is **offsite** and reachable (S3 / object store), not the same
      host as the DB.
- [ ] A2. Confirm the **encryption key used for the last full backup** is available in the
      key vault (or `KMS_BACKEND` rotation for the corresponding window).
- [ ] A3. Confirm the scratch restore environment (`DR-PG` Postgres 16) is provisioned and
      network-isolated (never reachable by real clients).
- [ ] A4. Announce the drill window to ops chat; no prod deploys during the drill.

## B. Snapshot & verify

- [ ] B1. Cause a **real** backup job run (`pg_dump` full or point-in-time WAL checkpoint).
- [ ] B2. Verify the artifact: expected size > 0, file exists, timestamp is within RPO target,
      extension/mime matches expectation.
- [ ] B3. Verify it is **encrypted** (header/`file` magic or wrapper check; do not gunzip raw PHI).
- [ ] B4. Record the backup `sha256` and retention window in the drill log.

## C. Restore & validate (the part that separates vendors from scripts)

- [ ] C1. Restore the latest full backup into `DR-PG` (fresh schema, no prod overlap).
- [ ] C2. Apply WAL / point-in-time replay if using PITR; verify it replays cleanly with no
      errors (this is the RPO proof — you should be able to restore to ~now).
- [ ] C3. Run integrity checks: `SELECT COUNT(*)` on the core tables and compare to prod-scale
      expectations; confirm **no orphaned FK rows**, **constraint check passes**.
- [ ] C4. **Tenant-isolation sanity**: pick two practices, confirm R1-R9-style rows are
      correctly scoped after restore (a restore that quietly merges tenants is a live incident).
- [ ] C5. Verify at least one **write path** works on the restored DB (create+rollback a patient),
      proving it's not just readable.
- [ ] C6. Measure **RTO**: elapsed wall-clock from "start restore" to "app passes `/health` with
      `database: connected`" on the scratch env. Record it. (Target ≤ 4 h; log the number.)
- [ ] C7. Check application boot on the restore: run the app against `DR-PG`, hit `/health`,
      confirm audit triggers still reject updates to `audit_logs` (write-once intact after
      restore).

## D. Teardown & evidence

- [ ] D1. Drop `DR-PG`; do **not** re-use it for real data.
- [ ] D2. Write the drill record (date, backup sha, table counts, RTO, restore-detection
      findings, any deviations) into `docs/dr-drill-log.md` (append-only).
- [ ] D3. Any deviation = a follow-up issue; nothing is "passed" with unclassified failures.
- [ ] D4. Sign-off: platform lead initials.

## E. Post-release variant (run after schema migrations)

Repeat B–C against the **new** backup, and additionally:
- [ ] E1. Confirm alembic `upgrade head` applies cleanly on the restored DB (no data drift).
- [ ] E2. Spot-check the newest tables/columns contain expected rows post-migration.