# 🚀 CoreDent PMS - Production Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Setup

#### Backend (.env.production)
```bash
cd coredent-api
cp .env.production .env

# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Edit .env and fill in all values
nano .env
```

#### Frontend (.env.production)
```bash
cd coredent-style-main
cp .env.production .env.production.local

# Edit and fill in production values
nano .env.production.local
```

### 2. Database Setup

```bash
# Create production database
createdb coredent_production

# Run migrations
cd coredent-api
alembic upgrade head

# Create admin user
python scripts/create_admin.py
```

### 3. SSL/TLS Certificates

```bash
# Using Let's Encrypt (recommended)
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Or use your own certificates
# Place them in:
# - coredent-api/ssl/cert.pem
# - coredent-api/ssl/key.pem
```

### 4. Update Dependencies

```bash
# Frontend
cd coredent-style-main
npm audit fix
npm update

# Backend
cd coredent-api
pip install --upgrade -r requirements.txt
```

## Deployment Steps

### Option 1: Docker Deployment (Recommended)

```bash
# 1. Build images
cd coredent-api
docker-compose -f docker-compose.prod.yml build

cd ../coredent-style-main
docker build -t coredent-frontend:latest .

# 2. Start services
cd ../coredent-api
docker-compose -f docker-compose.prod.yml up -d

# 3. Check logs
docker-compose -f docker-compose.prod.yml logs -f

# 4. Verify health
curl http://localhost:3000/health
```

### Option 2: Manual Deployment

#### Backend
```bash
cd coredent-api

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start with gunicorn (production)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:3000 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --log-level info
```

#### Frontend
```bash
cd coredent-style-main

# Build for production
npm run build

# Serve with nginx (see nginx.conf)
# Or deploy to CDN (Cloudflare, AWS CloudFront)
```

## Post-Deployment

### 1. Verify Deployment

```bash
# Check API health
curl https://api.yourdomain.com/health

# Check frontend
curl https://yourdomain.com

# Test login
# Visit https://yourdomain.com and try logging in
```

### 2. Set Up Monitoring

```bash
# Configure Sentry
# - Add SENTRY_DSN to .env files
# - Verify errors are being tracked

# Set up uptime monitoring
# - UptimeRobot, Pingdom, or similar
# - Monitor: /health endpoint

# Configure alerts
# - Email/SMS for downtime
# - Slack/Discord webhooks
```

### 3. Set Up Backups

```bash
# Add to crontab (daily at 2 AM)
crontab -e

# Add this line:
0 2 * * * /path/to/coredent-api/scripts/backup_database.sh >> /var/log/coredent-backup.log 2>&1

# Test backup
./scripts/backup_database.sh

# Test restore
./scripts/restore_database.sh /backups/coredent_backup_YYYYMMDD_HHMMSS.sql.gz
```

### 4. Configure Firewall

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# Restrict database access
# Only allow from application server IP
```

## Monitoring & Maintenance

### Daily Tasks
- Check error logs
- Monitor disk space
- Verify backups completed

### Weekly Tasks
- Review Sentry errors
- Check performance metrics
- Update dependencies (if needed)

### Monthly Tasks
- Rotate secrets/keys
- Review access logs
- Security audit
- Load testing

## Rollback Procedure

### If deployment fails:

```bash
# 1. Stop new version
docker-compose -f docker-compose.prod.yml down

# 2. Restore database (if needed)
./scripts/restore_database.sh /backups/coredent_backup_LATEST.sql.gz

# 3. Start previous version
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify rollback
curl https://api.yourdomain.com/health
```

## Troubleshooting

### API not responding
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Check if running
docker ps

# Restart service
docker-compose -f docker-compose.prod.yml restart api
```

### Database connection errors
```bash
# Check database is running
docker-compose -f docker-compose.prod.yml ps postgres

# Check connection
psql -h localhost -U coredent_user -d coredent_production

# Check logs
docker-compose -f docker-compose.prod.yml logs postgres
```

### High memory usage
```bash
# Check resource usage
docker stats

# Adjust worker count in docker-compose.prod.yml
# Restart services
```

## Security Hardening

### 1. Enable HTTPS Only
- Configure SSL/TLS certificates
- Redirect HTTP to HTTPS
- Enable HSTS headers

### 2. Database Security
- Use strong passwords
- Restrict network access
- Enable SSL connections
- Regular backups

### 3. Application Security
- Keep dependencies updated
- Enable rate limiting
- Monitor for suspicious activity
- Regular security audits

### 4. Server Security
- Keep OS updated
- Configure firewall
- Disable root SSH
- Use SSH keys only
- Enable fail2ban

## Performance Optimization

### 1. Database
```sql
-- Add indexes for common queries
CREATE INDEX idx_patient_email ON patient(email);
CREATE INDEX idx_appointment_date ON appointment(start_time);

-- Analyze tables
ANALYZE;
```

### 2. Caching
- Enable Redis caching
- Configure CDN for static assets
- Use browser caching headers

### 3. Load Balancing
- Use multiple API instances
- Configure nginx load balancer
- Enable health checks

## Support & Resources

- Documentation: https://docs.yourdomain.com
- Support Email: support@yourdomain.com
- Emergency Contact: +1-XXX-XXX-XXXX

## Compliance

### HIPAA Requirements
- ✅ Audit logging enabled
- ✅ Encryption at rest and in transit
- ✅ Access controls configured
- ✅ Session timeout enforced
- ✅ Password complexity enforced
- ⚠️ BAA agreements with vendors
- ⚠️ Staff HIPAA training
- ⚠️ Incident response plan

### Regular Compliance Tasks
- Monthly security reviews
- Quarterly risk assessments
- Annual HIPAA audits
- Vendor BAA renewals
