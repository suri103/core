# Offsite database backups

A one-shot Railway cron service that dumps the database, verifies the archive,
and uploads it to a dedicated S3 bucket.

**Why this is a separate image and not part of `coredent-api`.** `pg_dump`
refuses to dump a server whose major version is newer than its own
(`server version mismatch`). The API image is based on Debian bookworm, which
ships `postgresql-client` 15, while the database is PostgreSQL 16. Satisfying
that inside the API image would mean adding the third-party PGDG apt repository
to a HIPAA production image — and it would also put a full database dump on the
same CPU and IO as the API. The official `postgres:16` image sidesteps both.

## What it does

1. `pg_dump --format=custom`
2. Fails if the archive is empty
3. **Validates the archive with `pg_restore --list` before uploading** — a dump
   truncated by a full disk or a killed process must never be published as a
   restorable backup
4. Writes a `.sha256` sidecar
5. Uploads `coredent_<stamp>.dump`, its `.sha256`, and the rolling
   `latest.dump` pointer that `scripts/backup-dr-drill.ps1` expects

Any failure exits non-zero, so the platform marks the run failed instead of
recording a silent green run with no backup. The local copy is removed on exit
via a `trap`, so a dump never lingers as an unencrypted file on the host.

## 1. Create the bucket

Use a bucket dedicated to backups. Never reuse the patient-uploads bucket: a
misconfiguration or a compromised app credential must not be able to reach the
backups.

```bash
export BUCKET=coredent-backups
export REGION=us-east-1

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"

# Backups must never be world-readable.
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Versioning: a bad or interrupted write must not destroy the previous good dump.
aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

# Encryption at rest.
aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
```

Retention — `lifecycle.json`:

```json
{
  "Rules": [
    {
      "ID": "expire-old-backups",
      "Status": "Enabled",
      "Filter": { "Prefix": "database/" },
      "Expiration": { "Days": 35 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 90 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 }
    }
  ]
}
```

```bash
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" \
  --lifecycle-configuration file://lifecycle.json
```

Keep this window consistent with `docs/DATA_RETENTION_POLICY.md`. 35 daily
copies is the operational floor; extend it if the policy review requires more.

## 2. Create a write-only IAM user

The job only ever needs to write. Reads (for a restore or a drill) should use a
separate credential, so a compromised backup job cannot exfiltrate the history.

`policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
      "Resource": "arn:aws:s3:::coredent-backups/database/*"
    }
  ]
}
```

```bash
aws iam create-user --user-name coredent-backup-writer
aws iam put-user-policy --user-name coredent-backup-writer \
  --policy-name coredent-backup-putonly --policy-document file://policy.json
aws iam create-access-key --user-name coredent-backup-writer
```

Put the resulting key pair into Railway's variable editor only. It must never
be committed — this repository is public.

## 3. Create the Railway cron service

1. Same project → **New** → **Deploy from GitHub repo** → same repo, `master`
2. **Root Directory: `/backup`** (Railway then uses `backup/Dockerfile`)
3. **Do not** add a public domain — this service must not be reachable
4. Variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
   | `BACKUP_S3_BUCKET` | `coredent-backups` |
   | `AWS_REGION` | `us-east-1` |
   | `AWS_ACCESS_KEY_ID` | from step 2 |
   | `AWS_SECRET_ACCESS_KEY` | from step 2 |

   The `${{Postgres...}}` reference only resolves if the Postgres service is
   literally named `Postgres`. Rename it or fix the reference.

5. Set the cron schedule. **The schedule is your RPO** — `docs/BACKUP_DR_RUNBOOK.md`
   claims RPO ≤ 1h, so:

   ```
   0 * * * *
   ```

6. Set the restart policy to **never**. This is a one-shot job; a service that
   stays up would be billed as always-on and would never surface a failed run.

## 4. Verify — do not skip this

A backup that has never been restored is a hypothesis, not a backup.

```bash
# Watch a manual run in the Railway service logs, then:
aws s3 ls s3://coredent-backups/database/
# expect: coredent_<stamp>.dump, coredent_<stamp>.dump.sha256, latest.dump
```

Then restore it for real. This needs `psql`, `pg_restore` and a scratch
PostgreSQL instance (never point the target at production):

```powershell
aws s3 cp s3://coredent-backups/database/latest.dump $env:TEMP\latest.dump

pwsh scripts/backup-dr-drill.ps1 `
  -SourceDump "$env:TEMP\latest.dump" `
  -TargetPgDbUrl "postgresql://dr:dr@localhost:5433/dr" `
  -ProdDbUrl "<the real DATABASE_URL>"
```

The drill restores into the scratch DB, measures RTO against the 4h ceiling,
checks row counts on the core tables, and asserts the audit write-once trigger
survived the restore. Record the observed RTO/RPO — the runbook asks for it
monthly and there is currently no recorded number.

## Gotchas

- **Client/server version.** `pg_dump` must be equal to or newer than the
  server. This is the entire reason for the `postgres:16` base. If the database
  is ever upgraded, bump this image in the same change.
- **`latest.dump` is a convenience pointer**, not the backup. Restores for
  audit purposes should name a specific `<stamp>.dump`.
- **Region.** Keep the bucket in the same region as the database; cross-region
  transfers are slow and billed.
- **`docs/BACKUP_DR_RUNBOOK.md` is aspirational.** It describes hourly backups,
  CloudWatch/PagerDuty alerting, and `scripts/reencrypt_data.py` /
  `scripts/verify_encryption.py` — none of which exist. Treat this file as the
  accurate description of what is actually deployed.
- **Local builds on Windows.** `core.autocrlf=true` rewrites shell scripts to
  CRLF, which breaks the shebang in a container. `.gitattributes` pins `*.sh`
  to LF; keep it that way.
