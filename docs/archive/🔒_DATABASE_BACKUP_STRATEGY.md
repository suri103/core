# 🔒 DATABASE BACKUP STRATEGY

**Date**: April 13, 2026  
**Platform**: Railway PostgreSQL  
**Status**: ✅ Automatic Backups Enabled (Railway Default)

---

## ✅ Railway Automatic Backups (Already Active)

Railway provides **automatic daily backups** for PostgreSQL databases:

- **Frequency**: Daily automatic backups
- **Retention**: 7 days (free tier) / 30 days (paid tier)
- **Location**: Railway's secure infrastructure
- **Recovery**: Point-in-time restore via Railway dashboard

### How to Access Backups in Railway Dashboard:

1. Go to https://railway.app
2. Select your project: **practical-dream**
3. Click on your **PostgreSQL** service
4. Go to **"Backups"** tab
5. View available backups and restore points

---

## 📋 Additional Backup Strategy (Recommended)

For production SaaS, implement **3-2-1 backup rule**:
- **3** copies of data
- **2** different storage types
- **1** offsite backup

### Option 1: Manual Database Dumps (Weekly)

**Setup automated weekly backups via GitHub Actions**:

```yaml
# .github/workflows/backup-database.yml
name: Weekly Database Backup

on:
  schedule:
    - cron: '0 2 * * 0'  # Every Sunday at 2 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - name: Install Railway CLI
        run: npm install -g @railway/cli
      
      - name: Backup Database
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          # Connect to Railway and dump database
          railway run pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
      
      - name: Upload to S3
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws s3 cp backup_$(date +%Y%m%d).sql s3://coredent-backups/database/
      
      - name: Cleanup old backups (keep 30 days)
        run: |
          aws s3 ls s3://coredent-backups/database/ | \
          awk '{print $4}' | \
          head -n -30 | \
          xargs -I {} aws s3 rm s3://coredent-backups/database/{}
```

### Option 2: Railway CLI Manual Backup

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Create backup
railway run pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Compress backup
gzip backup_$(date +%Y%m%d).sql

# Upload to S3 or Google Drive
aws s3 cp backup_$(date +%Y%m%d).sql.gz s3://coredent-backups/
```

### Option 3: Automated Python Script

Create `scripts/backup_database.py`:

```python
#!/usr/bin/env python3
"""
Automated Database Backup Script
Run daily via cron or GitHub Actions
"""

import os
import subprocess
from datetime import datetime
import boto3
from pathlib import Path

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
S3_BUCKET = 'coredent-backups'
BACKUP_DIR = Path('/tmp/backups')
RETENTION_DAYS = 30

def create_backup():
    """Create PostgreSQL backup"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f'coredent_backup_{timestamp}.sql'
    
    # Create backup directory
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # Run pg_dump
    print(f"Creating backup: {backup_file}")
    subprocess.run([
        'pg_dump',
        DATABASE_URL,
        '-f', str(backup_file),
        '--no-owner',
        '--no-acl'
    ], check=True)
    
    # Compress backup
    print("Compressing backup...")
    subprocess.run(['gzip', str(backup_file)], check=True)
    
    return f"{backup_file}.gz"

def upload_to_s3(backup_file):
    """Upload backup to S3"""
    s3 = boto3.client('s3')
    key = f"database/{Path(backup_file).name}"
    
    print(f"Uploading to S3: {S3_BUCKET}/{key}")
    s3.upload_file(backup_file, S3_BUCKET, key)
    
    return key

def cleanup_old_backups():
    """Remove backups older than RETENTION_DAYS"""
    s3 = boto3.client('s3')
    
    # List all backups
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix='database/')
    
    if 'Contents' not in response:
        return
    
    # Sort by date
    backups = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    
    # Keep only recent backups
    for backup in backups[RETENTION_DAYS:]:
        print(f"Deleting old backup: {backup['Key']}")
        s3.delete_object(Bucket=S3_BUCKET, Key=backup['Key'])

def main():
    print("=== CoreDent Database Backup ===")
    print(f"Timestamp: {datetime.now()}")
    
    # Create backup
    backup_file = create_backup()
    print(f"✅ Backup created: {backup_file}")
    
    # Upload to S3
    s3_key = upload_to_s3(backup_file)
    print(f"✅ Uploaded to S3: {s3_key}")
    
    # Cleanup old backups
    cleanup_old_backups()
    print("✅ Cleanup complete")
    
    # Remove local backup
    os.remove(backup_file)
    print("✅ Local backup removed")
    
    print("=== Backup Complete ===")

if __name__ == '__main__':
    main()
```

**Run via cron** (on a server):
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /usr/bin/python3 /path/to/scripts/backup_database.py >> /var/log/coredent_backup.log 2>&1
```

---

## 🔄 Restore Procedures

### Restore from Railway Backup:

1. Go to Railway Dashboard → PostgreSQL → Backups
2. Select backup date
3. Click "Restore"
4. Confirm restoration

### Restore from Manual Backup:

```bash
# Download backup from S3
aws s3 cp s3://coredent-backups/database/backup_20260413.sql.gz .

# Decompress
gunzip backup_20260413.sql.gz

# Restore to Railway database
railway run psql $DATABASE_URL < backup_20260413.sql
```

---

## 🧪 Test Backup Recovery (Quarterly)

**Create test restoration procedure**:

```bash
# 1. Create test database
railway run psql $DATABASE_URL -c "CREATE DATABASE coredent_test;"

# 2. Restore backup to test database
railway run psql postgresql://user:pass@host/coredent_test < backup.sql

# 3. Verify data integrity
railway run psql postgresql://user:pass@host/coredent_test -c "SELECT COUNT(*) FROM patients;"

# 4. Drop test database
railway run psql $DATABASE_URL -c "DROP DATABASE coredent_test;"
```

---

## 📊 Backup Monitoring

**Setup alerts for backup failures**:

1. **Sentry Integration**: Log backup success/failure
2. **Email Alerts**: Send email on backup failure
3. **Slack Notifications**: Post to #ops channel

**Add to backup script**:
```python
import sentry_sdk

try:
    main()
    sentry_sdk.capture_message("Database backup successful", level="info")
except Exception as e:
    sentry_sdk.capture_exception(e)
    send_alert_email("Backup failed: " + str(e))
    raise
```

---

## 💰 Cost Estimate

| Service | Cost | Notes |
|---------|------|-------|
| Railway Backups | Free | 7-day retention (included) |
| S3 Storage (100GB) | $2.30/month | Additional offsite backups |
| S3 Requests | $0.50/month | Upload/download costs |
| **Total** | **~$3/month** | For comprehensive backup strategy |

---

## ✅ Backup Checklist

- [x] Railway automatic backups enabled (default)
- [ ] Setup weekly manual backups to S3
- [ ] Configure backup monitoring/alerts
- [ ] Test restore procedure (quarterly)
- [ ] Document recovery procedures
- [ ] Train team on restore process

---

## 🚨 Emergency Recovery Plan

**If database is corrupted or lost**:

1. **Immediate Actions** (5 minutes):
   - Stop all write operations
   - Notify team via Slack
   - Check Railway backup availability

2. **Restore from Railway** (15 minutes):
   - Go to Railway Dashboard → Backups
   - Select most recent backup
   - Click "Restore"
   - Wait for restoration

3. **Verify Data Integrity** (10 minutes):
   - Check patient count
   - Verify recent appointments
   - Test login functionality
   - Check audit logs

4. **Resume Operations** (5 minutes):
   - Restart backend service
   - Test critical workflows
   - Notify team of restoration

**Total Recovery Time**: ~35 minutes

---

## 📞 Support Contacts

- **Railway Support**: https://railway.app/help
- **Database Admin**: [Your email]
- **Emergency Hotline**: [Your phone]

---

**Status**: ✅ Railway automatic backups active  
**Next Action**: Setup weekly S3 backups (optional)  
**Review Date**: Quarterly (every 3 months)
