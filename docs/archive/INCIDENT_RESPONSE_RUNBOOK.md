# 🚨 CoreDent PMS - Incident Response Runbook

## Severity Levels

- **P0 (Critical)**: Complete system outage, data breach
- **P1 (High)**: Major feature broken, significant performance degradation
- **P2 (Medium)**: Minor feature broken, some users affected
- **P3 (Low)**: Cosmetic issues, no user impact

## Incident Response Process

### 1. Detection & Alert
- Monitor alerts from Sentry, uptime monitoring
- User reports via support channels
- Automated health checks

### 2. Initial Response (5 minutes)
1. Acknowledge the incident
2. Assess severity level
3. Notify team (if P0/P1)
4. Start incident log

### 3. Investigation (15-30 minutes)
1. Check system status
2. Review error logs
3. Identify root cause
4. Document findings

### 4. Resolution
1. Implement fix
2. Test in staging (if possible)
3. Deploy to production
4. Verify resolution

### 5. Post-Incident
1. Write incident report
2. Conduct post-mortem
3. Implement preventive measures
4. Update documentation

## Common Incidents

### API Not Responding (P0)

**Symptoms:**
- Health check failing
- 502/503 errors
- Timeout errors

**Quick Checks:**
```bash
# Check if service is running
docker ps | grep coredent-api

# Check logs
docker logs coredent-api-prod --tail 100

# Check resource usage
docker stats coredent-api-prod
```

**Resolution Steps:**
1. Restart service: `docker-compose restart api`
2. If still failing, check database connection
3. Check disk space: `df -h`
4. Check memory: `free -m`
5. Scale up if needed

### Database Connection Errors (P0)

**Symptoms:**
- "Connection refused" errors
- "Too many connections" errors
- Slow queries

**Quick Checks:**
```bash
# Check database status
docker ps | grep postgres

# Check connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check slow queries
psql -c "SELECT query, state, wait_event FROM pg_stat_activity WHERE state != 'idle';"
```

**Resolution Steps:**
1. Restart database: `docker-compose restart postgres`
2. Kill long-running queries if needed
3. Increase connection pool size
4. Check for connection leaks

### High Error Rate (P1)

**Symptoms:**
- Sentry alert for high error rate
- Multiple user reports
- Specific endpoint failing

**Quick Checks:**
```bash
# Check recent errors in Sentry
# Review error patterns

# Check API logs
docker logs coredent-api-prod | grep ERROR

# Check specific endpoint
curl -v https://api.yourdomain.com/api/v1/patients
```

**Resolution Steps:**
1. Identify failing endpoint/feature
2. Check recent deployments
3. Rollback if needed
4. Fix and redeploy

### Slow Performance (P1)

**Symptoms:**
- Response times > 2 seconds
- User complaints about slowness
- High CPU/memory usage

**Quick Checks:**
```bash
# Check resource usage
docker stats

# Check database performance
psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check API response times
./monitoring/performance_check.py
```

**Resolution Steps:**
1. Identify slow queries
2. Add database indexes
3. Enable caching
4. Scale horizontally if needed

### Data Breach / Security Incident (P0)

**Immediate Actions:**
1. **DO NOT PANIC**
2. Isolate affected systems
3. Preserve evidence
4. Notify security team
5. Follow HIPAA breach notification procedures

**Investigation:**
1. Identify scope of breach
2. Determine what data was accessed
3. Review access logs
4. Document timeline

**Notification:**
- Affected users (within 60 days per HIPAA)
- HHS Office for Civil Rights (if >500 users)
- Media (if >500 users)
- Law enforcement (if criminal)

## Emergency Contacts

- **On-Call Engineer**: [Phone]
- **Database Admin**: [Phone]
- **Security Team**: [Phone]
- **Legal/Compliance**: [Phone]
- **CEO/Management**: [Phone]

## Useful Commands

### Docker
```bash
# View all containers
docker ps -a

# Restart service
docker-compose restart [service]

# View logs
docker logs [container] --tail 100 -f

# Execute command in container
docker exec -it [container] bash
```

### Database
```bash
# Connect to database
psql $DATABASE_URL

# Check active connections
SELECT count(*) FROM pg_stat_activity;

# Kill connection
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = [pid];

# Vacuum database
VACUUM ANALYZE;
```

### System
```bash
# Check disk space
df -h

# Check memory
free -m

# Check CPU
top

# Check network
netstat -tulpn
```

## Rollback Procedure

```bash
# 1. Stop current version
docker-compose down

# 2. Restore database backup
./scripts/restore_database.sh /backups/latest.sql.gz

# 3. Deploy previous version
git checkout [previous-tag]
docker-compose up -d

# 4. Verify
curl https://api.yourdomain.com/health
```

## Post-Incident Template

```markdown
# Incident Report: [Title]

**Date**: YYYY-MM-DD
**Severity**: P0/P1/P2/P3
**Duration**: X hours Y minutes
**Impact**: X users affected

## Summary
Brief description of what happened

## Timeline
- HH:MM - Incident detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Incident resolved

## Root Cause
What caused the incident

## Resolution
How it was fixed

## Prevention
What we'll do to prevent this in the future

## Action Items
- [ ] Item 1
- [ ] Item 2
```
