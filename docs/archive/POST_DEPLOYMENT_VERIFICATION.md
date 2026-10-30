# Post-Deployment Verification Guide

## 🔍 Immediate Checks (First 5 minutes)

### 1. Service Status
```bash
# Check if services are running
curl -I https://coredent.app
curl -I https://api.coredent.app

# Expected: HTTP 200 or 301 (redirect)
```

### 2. API Health Check
```bash
# Backend health endpoint
curl https://api.coredent.app/health

# Expected response:
# {"status": "healthy", "timestamp": "2026-04-07T..."}
```

### 3. Frontend Load
```bash
# Check if frontend loads
curl https://coredent.app | head -20

# Expected: HTML with React app
```

---

## 🧪 Functional Tests (First 15 minutes)

### 1. Authentication Flow
```bash
# Test login endpoint
curl -X POST https://api.coredent.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "your_password"
  }'

# Expected: JWT token in response
```

### 2. Patient Endpoints
```bash
# List patients (requires auth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.coredent.app/api/v1/patients

# Expected: 200 OK with patient list
```

### 3. Database Connectivity
```bash
# Check if database queries work
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.coredent.app/api/v1/appointments

# Expected: 200 OK with appointments
```

---

## 📊 Performance Checks (First 30 minutes)

### 1. Response Times
```bash
# Measure API response time
time curl https://api.coredent.app/health

# Expected: < 500ms
```

### 2. Frontend Performance
- Open browser DevTools (F12)
- Go to Network tab
- Reload page
- Check:
  - Main bundle loads
  - CSS loads
  - JavaScript executes
  - No 404 errors

### 3. Database Performance
```bash
# Check slow queries (if available)
# Monitor database logs for slow queries
# Expected: No queries > 1 second
```

---

## 🔐 Security Verification

### 1. HTTPS/TLS
```bash
# Verify SSL certificate
curl -v https://api.coredent.app 2>&1 | grep "SSL"

# Expected: SSL certificate valid
```

### 2. Security Headers
```bash
# Check security headers
curl -I https://api.coredent.app | grep -i "security\|x-\|content-"

# Expected headers:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# Strict-Transport-Security: max-age=...
```

### 3. CORS Configuration
```bash
# Test CORS headers
curl -H "Origin: https://coredent.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -X OPTIONS https://api.coredent.app/api/v1/auth/login

# Expected: CORS headers present
```

---

## 📈 Monitoring Setup

### 1. Error Tracking
- [ ] Sentry configured
- [ ] Error alerts enabled
- [ ] Slack notifications working

### 2. Performance Monitoring
- [ ] Web Vitals tracking enabled
- [ ] API response time monitoring
- [ ] Database query monitoring

### 3. Uptime Monitoring
- [ ] Uptime robot configured
- [ ] Health check endpoint monitored
- [ ] Alerts configured

---

## 🚨 Troubleshooting

### Frontend Not Loading
1. Check Railway frontend service logs
2. Verify environment variables
3. Check browser console for errors
4. Clear browser cache

### API Not Responding
1. Check Railway backend service logs
2. Verify database connection
3. Check environment variables
4. Review error logs

### Database Connection Failed
1. Verify DATABASE_URL is set
2. Check PostgreSQL is running
3. Verify network connectivity
4. Check database credentials

### Authentication Not Working
1. Verify JWT_SECRET is set
2. Check ENCRYPTION_KEY is set
3. Verify user exists in database
4. Check token expiration

---

## ✅ Sign-Off Checklist

- [ ] Services deployed successfully
- [ ] Health checks passing
- [ ] Authentication working
- [ ] Database queries working
- [ ] API endpoints responding
- [ ] Frontend loading
- [ ] Security headers present
- [ ] No console errors
- [ ] Performance acceptable
- [ ] Monitoring configured

---

## 📞 Escalation Path

**Issue**: Services not starting
- **Action**: Check Railway logs
- **Contact**: DevOps team

**Issue**: Database connection failed
- **Action**: Verify DATABASE_URL
- **Contact**: Database admin

**Issue**: Authentication failing
- **Action**: Check JWT_SECRET
- **Contact**: Backend team

**Issue**: Frontend not loading
- **Action**: Check build artifacts
- **Contact**: Frontend team

---

## 📝 Deployment Notes

**Deployment Time**: _______________
**Deployed By**: _______________
**Status**: _______________
**Issues Encountered**: _______________
**Resolution**: _______________

---

**Deployment verification complete!** ✅
