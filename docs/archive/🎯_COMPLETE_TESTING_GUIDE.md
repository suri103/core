# 🎯 Complete Testing Guide - Application Ready

## Deployment Summary
| Component | URL | Status |
|-----------|-----|--------|
| Backend API | https://coredentist-production.up.railway.app | ✅ Running |
| Frontend | https://heartfelt-benevolence-production-ba39.up.railway.app | ✅ Running |
| Database | PostgreSQL (Railway) | ✅ Connected |
| CORS | Configured | ✅ Ready |

---

## Step 1: Create Test Admin User

### Option A: Using Python Script (Recommended)

```bash
cd coredent-api
python scripts/create_admin.py
```

This will create:
- **Email**: admin@coredent.com
- **Password**: Admin123!
- **Role**: Owner
- **Practice**: Demo Dental Practice

### Option B: Manual SQL (If script fails)

Connect to Railway PostgreSQL and run:
```sql
INSERT INTO "user" (id, email, password_hash, first_name, last_name, role, practice_id, is_active, created_at)
VALUES (
  gen_random_uuid(),
  'admin@coredent.com',
  '$2b$12$...',  -- bcrypt hash of "Admin123!"
  'Admin',
  'User',
  'owner',
  (SELECT id FROM practice LIMIT 1),
  true,
  NOW()
);
```

---

## Step 2: Test Frontend Access

### 2.1 Open Frontend
1. Go to: https://heartfelt-benevolence-production-ba39.up.railway.app
2. You should see login page
3. Open DevTools (F12)
4. Go to Console tab

### 2.2 Check for Errors
- Should have NO red errors
- May have yellow warnings (OK)
- Look for CORS errors specifically

---

## Step 3: Test Login

### 3.1 Enter Credentials
- **Email**: admin@coredent.com
- **Password**: Admin123!

### 3.2 Watch Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Click Login
4. Watch for API calls to backend
5. Look for:
   - ✅ POST /api/v1/auth/login (200 status)
   - ✅ Response contains access_token

### 3.3 Check for CORS Errors
If you see error like:
```
Access to XMLHttpRequest at 'https://coredentist-production.up.railway.app/api/v1/auth/login' 
from origin 'https://heartfelt-benevolence-production-ba39.up.railway.app' 
has been blocked by CORS policy
```

**Solution**: Go to Railway backend service and verify CORS_ORIGINS is set to:
```
https://heartfelt-benevolence-production-ba39.up.railway.app
```

---

## Step 4: Test Dashboard

### 4.1 After Login
- Should redirect to dashboard
- Dashboard should load without errors
- Should see welcome message

### 4.2 Check Data Loading
- Look at Network tab
- Should see API calls to:
  - `/api/v1/patients` (patient list)
  - `/api/v1/appointments` (appointments)
  - `/api/v1/dashboard` (dashboard data)

### 4.3 Verify Data Displays
- Patient count should show
- Upcoming appointments should display
- Charts/stats should render

---

## Step 5: Test Navigation

Try clicking on each page:

### Pages to Test
1. **Dashboard** - Should load stats and charts
2. **Patients** - Should load patient list
3. **Appointments** - Should load appointments
4. **Schedule** - Should load calendar
5. **Billing** - Should load billing data
6. **Insurance** - Should load insurance info
7. **Reports** - Should load reports
8. **Settings** - Should load settings

### Expected Behavior
- Each page loads without errors
- Data displays from backend
- No CORS errors in console
- No 401/403/500 errors in Network tab

---

## Step 6: Test API Directly

### 6.1 Test Backend Health
```bash
curl https://coredentist-production.up.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "CoreDent API",
  "version": "1.0.0",
  "environment": "production"
}
```

### 6.2 Test Login API
```bash
curl -X POST https://coredentist-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@coredent.com",
    "password": "Admin123!"
  }'
```

Expected response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "email": "admin@coredent.com",
    "first_name": "Admin",
    "last_name": "User"
  }
}
```

---

## Troubleshooting

### Issue: Login Page Doesn't Load
- **Check**: Frontend URL is correct
- **Check**: Browser console for errors
- **Check**: Network tab for failed requests
- **Solution**: Clear cache, try incognito window

### Issue: Login Fails with 401
- **Check**: Email and password are correct
- **Check**: User exists in database
- **Solution**: Create new admin user with script

### Issue: CORS Error
- **Check**: Frontend URL in backend CORS_ORIGINS
- **Check**: URL matches exactly (including https://)
- **Solution**: Update CORS_ORIGINS in Railway backend variables

### Issue: API Returns 500
- **Check**: Backend logs in Railway
- **Check**: Database connection
- **Solution**: Check Railway backend logs for errors

### Issue: Data Doesn't Load
- **Check**: Network tab for failed API calls
- **Check**: API response status codes
- **Check**: Browser console for errors
- **Solution**: Check backend logs

---

## Success Criteria

✅ All tests pass when:
1. Frontend loads without errors
2. Backend health check works
3. Can login with test credentials
4. Dashboard loads and displays data
5. All pages load without CORS errors
6. API calls return 200 status
7. No red errors in console

---

## Next Steps

### If All Tests Pass:
1. Create additional test users
2. Test all features thoroughly
3. Monitor logs for errors
4. Set up monitoring/alerts
5. Plan data migration strategy

### If Tests Fail:
1. Check specific error message
2. Review troubleshooting section
3. Check Railway logs
4. Report exact error to support

---

## Important Notes

- ⚠️ Change admin password after first login
- ⚠️ Don't use test credentials in production
- ⚠️ Monitor logs for security issues
- ⚠️ Set up backups for database
- ⚠️ Enable HTTPS everywhere (Railway handles this)

---

## Support

If you encounter issues:
1. Check Railway logs
2. Check browser console
3. Check Network tab
4. Review error messages carefully
5. Try clearing cache and cookies
