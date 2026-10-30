# Production Deployment Checklist - CoreDent PMS

## Pre-Deployment Verification

### Frontend
- [ ] `npm run build` completes successfully
- [ ] `dist/` folder created with all assets
- [ ] No console errors in build output
- [ ] Bundle size reasonable (<5MB gzipped)
- [ ] All 172 tests passing
- [ ] No security vulnerabilities (`npm audit`)

### Backend
- [ ] All imports fixed and verified
- [ ] Database migrations run successfully
- [ ] Backend tests passing (or documented as skipped)
- [ ] Environment variables configured
- [ ] ENCRYPTION_KEY set in production
- [ ] Database connection verified

### Infrastructure
- [ ] Railway project created
- [ ] GitHub repository connected
- [ ] Environment variables added to Railway
- [ ] Docker images build successfully
- [ ] Health check endpoints responding

---

## Deployment Steps

### 1. Prepare Frontend
```bash
cd coredent-style-main
npm run build
# Verify dist/ folder exists
ls -la dist/
```

### 2. Prepare Backend
```bash
cd coredent-api
# Run migrations
python -m alembic upgrade head
# Verify database
python -m pytest tests/ -v
```

### 3. Push to GitHub
```bash
git add -A
git commit -m "Production deployment - all tests passing"
git push origin main
```

### 4. Deploy to Railway
- Go to Railway dashboard
- Select CoreDent project
- Trigger deployment from GitHub
- Monitor logs for errors

### 5. Post-Deployment Verification
```bash
# Test API health
curl https://api.coredent.app/health

# Test frontend
curl https://coredent.app

# Test login
curl -X POST https://api.coredent.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'
```

---

## Rollback Plan

If deployment fails:

1. **Check Railway logs** for error messages
2. **Verify environment variables** are set correctly
3. **Check database connection** string
4. **Revert to previous commit** if needed:
   ```bash
   git revert HEAD
   git push origin main
   ```

---

## Post-Launch Monitoring

### Daily Checks
- [ ] API response times < 500ms
- [ ] Error rate < 0.1%
- [ ] Database queries optimized
- [ ] No security alerts

### Weekly Checks
- [ ] Backup database
- [ ] Review audit logs
- [ ] Check for failed requests
- [ ] Monitor resource usage

### Monthly Checks
- [ ] Security audit
- [ ] Performance optimization
- [ ] Dependency updates
- [ ] Disaster recovery drill

---

## Contact & Support

**Deployment Issues**: Check Railway dashboard logs
**Database Issues**: Review PostgreSQL logs
**Frontend Issues**: Check browser console
**API Issues**: Check FastAPI logs

---

## Sign-Off

- [ ] Frontend Lead: _______________
- [ ] Backend Lead: _______________
- [ ] DevOps Lead: _______________
- [ ] Product Manager: _______________

**Deployment Date**: _______________
**Deployed By**: _______________
**Status**: _______________
