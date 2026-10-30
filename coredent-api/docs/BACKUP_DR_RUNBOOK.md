# Backup & Disaster Recovery Runbook

**Last Updated:** 2026-01-06  
**Version:** 1.0  
**Owner:** DevOps Team  
**Review Frequency:** Quarterly

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Procedures](#recovery-procedures)
4. [Testing Procedures](#testing-procedures)
5. [Monitoring & Alerting](#monitoring--alerting)
6. [Contact Information](#contact-information)
7. [Incident Response](#incident-response)

---

## Overview

This runbook documents the backup and disaster recovery (DR) procedures for the CoreDent API production environment. It covers database backups, file storage backups, configuration backups, and recovery procedures for various failure scenarios.

**RPO (Recovery Point Objective):** 1 hour  
**RTO (Recovery Time Objective):** 4 hours

---

## Backup Strategy

### 1. Database Backups (PostgreSQL)

#### Automated Backups

**Frequency:** Every hour  
**Retention:** 30 days  
**Storage:** AWS S3 (encrypted at rest)  
**Tool:** `pg_dump` + `aws s3 cp`

#### Backup Script Location

```
/scripts/backup-database.sh
```

#### Manual Backup Command

```bash
#!/bin/bash
# Manual database backup

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/backups"
S3_BUCKET="s3://coredent-backups-prod/database"

# Create backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -f ${BACKUP_DIR}/coredent_${TIMESTAMP}.dump

# Upload to S3
aws s3 cp ${BACKUP_DIR}/coredent_${TIMESTAMP}.dump ${S3_BUCKET}/

# Verify upload
aws s3 ls ${S3_BUCKET}/coredent_${TIMESTAMP}.dump

# Cleanup local file
rm ${BACKUP_DIR}/coredent_${TIMESTAMP}.dump

echo "Backup completed: coredent_${TIMESTAMP}.dump"
```

#### Verify Backup Integrity

```bash
# Download latest backup
aws s3 cp s3://coredent-backups-prod/database/latest.dump /tmp/verify.dump

# Test restore to temporary database
pg_restore -h localhost -U postgres -d test_restore -c /tmp/verify.dump

# Verify data
psql -h localhost -U postgres -d test_restore -c "SELECT COUNT(*) FROM patients;"

# Cleanup
dropdb -h localhost -U postgres test_restore
rm /tmp/verify.dump
```

### 2. File Storage Backups (AWS S3)

#### Patient Documents & Images

**Source:** `s3://coredent-patient-files-prod/`  
**Backup Destination:** `s3://coredent-backups-prod/files/`  
**Frequency:** Daily at 2:00 AM UTC  
**Tool:** AWS S3 Cross-Region Replication + Lifecycle Policies

#### Enable Cross-Region Replication

```bash
# One-time setup (already configured)
aws s3api put-bucket-replication \
  --bucket coredent-patient-files-prod \
  --replication-configuration file://replication-config.json
```

#### Manual File Backup

```bash
#!/bin/bash
# Manual file storage backup

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SOURCE_BUCKET="s3://coredent-patient-files-prod/"
BACKUP_BUCKET="s3://coredent-backups-prod/files/${TIMESTAMP}/"

# Sync files
aws s3 sync ${SOURCE_BUCKET} ${BACKUP_BUCKET} --delete

# Verify sync
aws s3 ls ${BACKUP_BUCKET} --recursive | wc -l

echo "File backup completed to: ${BACKUP_BUCKET}"
```

### 3. Configuration Backups

#### Environment Variables

**Location:** Railway dashboard + Git repository  
**Frequency:** On every deployment  
**Tool:** Railway CLI + Git

```bash
# Export Railway environment variables
railway variables --service coredent-api > .env.backup.$(date +%Y%m%d)

# Commit to secure repository (encrypted)
git add .env.backup.*
git commit -m "Backup environment variables $(date +%Y%m%d)"
git push origin main
```

#### Application Code

**Location:** GitHub repository  
**Frequency:** On every commit  
**Retention:** Indefinite (Git history)

---

## Recovery Procedures

### Scenario 1: Database Corruption

**Symptoms:**
- Database queries failing
- Data integrity errors
- Application returning 500 errors on database operations

**Recovery Steps:**

```bash
# 1. Stop application to prevent further writes
railway stop coredent-api

# 2. Identify latest good backup
aws s3 ls s3://coredent-backups-prod/database/ | tail -5

# 3. Download backup
aws s3 cp s3://coredent-backups-prod/database/coredent_YYYYMMDD_HHMMSS.dump /tmp/restore.dump

# 4. Create new database (or drop existing)
railway run psql -h $DB_HOST -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS coredent_prod;"
railway run psql -h $DB_HOST -U $DB_USER -d postgres -c "CREATE DATABASE coredent_prod;"

# 5. Restore database
pg_restore -h $DB_HOST -U $DB_USER -d coredent_prod -c /tmp/restore.dump

# 6. Verify restore
psql -h $DB_HOST -U $DB_USER -d coredent_prod -c "SELECT COUNT(*) FROM patients;"
psql -h $DB_HOST -U $DB_USER -d coredent_prod -c "SELECT COUNT(*) FROM appointments;"

# 7. Run migrations (if needed)
railway run alembic upgrade head

# 8. Restart application
railway start coredent-api

# 9. Verify application health
curl -f https://api.coredent.com/health
```

**Estimated Time:** 2-3 hours

### Scenario 2: Complete Infrastructure Failure

**Symptoms:**
- All services down
- No access to Railway dashboard
- Network connectivity issues

**Recovery Steps:**

```bash
# 1. Provision new Railway project
railway init --name coredent-api-dr

# 2. Restore environment variables
railway variables --service coredent-api-dr < .env.backup.latest

# 3. Deploy application code
git clone https://github.com/coredent/coredent-api.git
cd coredent-api
railway up --service coredent-api-dr

# 4. Restore database (see Scenario 1, steps 2-6)

# 5. Restore file storage
aws s3 sync s3://coredent-backups-prod/files/latest/ s3://coredent-patient-files-dr/

# 6. Update DNS (if using custom domain)
# Update A/CNAME records to point to new Railway URL

# 7. Update CORS_ORIGINS in environment variables
railway variables set CORS_ORIGINS=https://new-domain.com

# 8. Verify all services
curl -f https://new-api-domain.com/health
```

**Estimated Time:** 4-6 hours

### Scenario 3: Ransomware / Malicious Data Deletion

**Symptoms:**
- Unusual data deletion patterns in audit logs
- Suspicious user activity
- Security alerts from monitoring

**Recovery Steps:**

```bash
# 1. IMMEDIATELY stop application
railway stop coredent-api

# 2. Isolate database (revoke application credentials)
railway run psql -h $DB_HOST -U $DB_USER -d postgres -c "REVOKE ALL PRIVILEGES ON DATABASE coredent_prod FROM coredent_app;"

# 3. Identify point of compromise from audit logs
railway logs coredent-api --tail 1000 | grep -i "delete\|drop\|truncate"

# 4. Restore database to point BEFORE compromise
# (Use backup from Scenario 1, but choose backup timestamp before incident)

# 5. Rotate ALL secrets
# - Database password
# - SECRET_KEY
# - ENCRYPTION_KEYS
# - AWS credentials
# - Stripe API keys

# 6. Update environment variables with new secrets
railway variables set DB_PASSWORD=new_secure_password
railway variables set SECRET_KEY=new_secret_key
# ... etc

# 7. Restart application
railway start coredent-api

# 8. Conduct security audit
# Review all user accounts
# Check for unauthorized access
# Verify no backdoors installed
```

**Estimated Time:** 6-8 hours

### Scenario 4: Encryption Key Compromise

**Symptoms:**
- Security alert about key exposure
- Unauthorized access to encrypted data
- Compliance violation notification

**Recovery Steps:**

```bash
# 1. Generate new encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Update ENCRYPTION_KEYS (add new key, keep old for decryption)
railway variables set ENCRYPTION_KEYS="current:NEW_KEY,previous:OLD_KEY"

# 3. Restart application
railway restart coredent-api

# 4. Re-encrypt all data with new key
railway run python scripts/reencrypt_data.py --from-key previous --to-key current

# 5. Verify re-encryption
railway run python scripts/verify_encryption.py

# 6. Remove old key from ENCRYPTION_KEYS
railway variables set ENCRYPTION_KEYS="current:NEW_KEY"

# 7. Restart application again
railway restart coredent-api

# 8. Verify application still works
curl -f https://api.coredent.com/health
```

**Estimated Time:** 4-6 hours

---

## Testing Procedures

### Monthly DR Test

**Schedule:** First Monday of each month, 2:00 AM UTC  
**Duration:** 2-3 hours  
**Participants:** DevOps team, on-call engineer

#### Test Checklist

- [ ] Restore database from latest backup to test environment
- [ ] Verify all tables and data present
- [ ] Test application startup with restored database
- [ ] Verify patient data can be read (encryption working)
- [ ] Test file storage restore (download sample patient files)
- [ ] Verify webhook endpoints work
- [ ] Test authentication flow
- [ ] Document any issues found
- [ ] Update runbook if procedures changed

#### Test Script

```bash
#!/bin/bash
# Monthly DR test script

TEST_ENV="dr-test-$(date +%Y%m%d)"

# Create test environment
railway init --name $TEST_ENV

# Restore latest backup
aws s3 cp s3://coredent-backups-prod/database/latest.dump /tmp/dr-test.dump
pg_restore -h $TEST_DB_HOST -U $TEST_DB_USER -d $TEST_DB_NAME -c /tmp/dr-test.dump

# Deploy application
cd coredent-api
railway up --service $TEST_ENV

# Run verification tests
pytest tests/test_dr_recovery.py

# Cleanup
railway delete $TEST_ENV
dropdb -h $TEST_DB_HOST -U $TEST_DB_USER $TEST_DB_NAME
```

### Quarterly Full DR Drill

**Schedule:** Every 3 months (January, April, July, October)  
**Duration:** 8 hours  
**Participants:** Full engineering team

#### Drill Scenarios

1. **Database corruption recovery** (2 hours)
2. **Complete infrastructure rebuild** (4 hours)
3. **Encryption key rotation** (2 hours)

#### Success Criteria

- All scenarios completed within RTO
- No data loss beyond RPO
- All team members can execute procedures
- Documentation is accurate and complete

---

## Monitoring & Alerting

### Backup Monitoring

**Tool:** AWS CloudWatch + Railway Monitoring  
**Alerts:**

| Metric | Threshold | Alert Channel |
|--------|-----------|---------------|
| Backup Success Rate | < 100% | PagerDuty |
| Backup Size Change | > 20% | Slack |
| Backup Age | > 2 hours | PagerDuty |
| S3 Storage Cost | > $100/month | Email |

### Verification Commands

```bash
# Check latest backup age
aws s3 ls s3://coredent-backups-prod/database/ | tail -1

# Verify backup integrity
aws s3 cp s3://coredent-backups-prod/database/latest.dump /tmp/verify.dump
pg_restore --list /tmp/verify.dump

# Check backup size trend
aws s3 ls s3://coredent-backups-prod/database/ --summarize --human-readable
```

---

## Contact Information

### Primary Contacts

| Role | Name | Email | Phone | PagerDuty |
|------|------|-------|-------|-----------|
| DevOps Lead | John Doe | john@coredent.com | +1-555-0100 | @john-doe |
| Database Admin | Jane Smith | jane@coredent.com | +1-555-0101 | @jane-smith |
| On-Call Engineer | (Rotating) | oncall@coredent.com | +1-555-0199 | @on-call |

### Escalation Path

1. **Level 1:** On-Call Engineer (15 min response)
2. **Level 2:** DevOps Lead (30 min response)
3. **Level 3:** CTO (1 hour response)

### External Vendors

| Vendor | Service | Support Contact | SLA |
|--------|---------|-----------------|-----|
| Railway | Hosting | support@railway.app | 4 hours |
| AWS | S3/Backup | AWS Support Portal | 4 hours |
| PostgreSQL | Database | Community Support | N/A |

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P1 - Critical** | Complete service outage | 15 minutes | Database down, all users affected |
| **P2 - High** | Partial service degradation | 1 hour | Slow queries, some features broken |
| **P3 - Medium** | Minor issues | 4 hours | Non-critical bugs, performance issues |
| **P4 - Low** | Cosmetic issues | 24 hours | UI glitches, documentation errors |

### Incident Communication

**Internal:**
- Slack: `#incident-response` channel
- Email: `incident@coredent.com`

**External:**
- Status page: https://status.coredent.com
- Customer email: `support@coredent.com`

### Post-Incident Review

**Timeline:** Within 48 hours of incident resolution  
**Participants:** All involved team members  
**Deliverables:**

- [ ] Incident timeline document
- [ ] Root cause analysis
- [ ] Action items to prevent recurrence
- [ ] Updated runbook (if needed)
- [ ] Customer communication (if applicable)

---

## Appendix

### A. Backup Verification Checklist

- [ ] Database backup file exists and is > 100MB
- [ ] Backup file can be restored without errors
- [ ] All tables present after restore
- [ ] Patient count matches expected value
- [ ] Encrypted fields can be decrypted
- [ ] File storage backup is complete
- [ ] Environment variables backup is current

### B. Recovery Time Estimates

| Scenario | Estimated Time | Complexity |
|----------|---------------|------------|
| Database restore | 2-3 hours | Medium |
| Complete rebuild | 4-6 hours | High |
| Key rotation | 4-6 hours | High |
| Ransomware recovery | 6-8 hours | Critical |

### C. Backup Storage Costs

| Service | Monthly Cost | Retention |
|---------|-------------|-----------|
| Database backups (S3) | ~$50 | 30 days |
| File backups (S3) | ~$100 | 90 days |
| Configuration backups | ~$5 | Indefinite |
| **Total** | **~$155** | |

### D. Useful Commands Reference

```bash
# List all backups
aws s3 ls s3://coredent-backups-prod/database/ --recursive

# Download specific backup
aws s3 cp s3://coredent-backups-prod/database/coredent_20260106_120000.dump /tmp/

# Check database size
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));"

# List all tables
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "\dt"

# Count records in table
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM patients;"

# Check encryption key status
railway run python -c "from app.core.encryption import encryption; print(encryption.cipher is not None)"
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-06 | DevOps Team | Initial version |

**Next Review Date:** 2026-04-06  
**Approved By:** CTO  
**Distribution:** Engineering Team, DevOps, Management