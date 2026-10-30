# ✅ Test Credentials & Application Testing Guide

## Test Admin User Created Successfully

**Status**: ✅ READY TO TEST

### Login Credentials

```
Email:    admin@coredent.com
Password: Admin123!
Role:     DENTIST
```

### Practice Information

```
Practice Name: Demo Dental Practice
Practice ID:   4463affd-9797-4a2e-9337-4d2b02038716
```

---

## Application URLs

| Component | URL |
|-----------|-----|
| **Frontend** | https://heartfelt-benevolence-production-ba39.up.railway.app |
| **Backend API** | https://coredentist-production.up.railway.app |
| **Health Check** | https://coredentist-production.up.railway.app/health |

---

## Testing Steps

### 1. Frontend Access
1. Open https://heartfelt-benevolence-production-ba39.up.railway.app in your browser
2. You should see the login page
3. Check browser console (F12) for any errors

### 2. Login Test
1. Enter email: `admin@coredent.com`
2. Enter password: `Admin123!`
3. Click "Sign In"
4. You should be redirected to the dashboard

### 3. Dashboard Verification
After successful login, verify:
- [ ] Dashboard loads without errors
- [ ] Navigation sidebar is visible
- [ ] User profile shows "Admin User"
- [ ] No CORS errors in console
- [ ] No 401/403 errors in network tab

### 4. API Connectivity Test
Open browser console and run:
```javascript
// Test backend connectivity
fetch('https://coredentist-production.up.railway.app/health')
  .then(r => r.json())
  .then(d => console.log('Health:', d))
  .catch(e => console.error('Error:', e))
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-23T...",
  "version": "1.0.0"
}
```

### 5. Common Issues & Solutions

**Issue**: Login page doesn't load
- Check frontend URL is correct
- Check browser console for errors
- Verify frontend service is running on Railway

**Issue**: Login fails with 401
- Verify credentials are correct
- Check backend is running (health check)
- Check CORS configuration in backend

**Issue**: CORS errors in console
- Verify `FRONTEND_URL` is set in backend environment
- Check `CORS_ORIGINS` includes frontend URL
- Restart backend service if needed

**Issue**: Dashboard loads but no data
- This is expected - no appointments/patients created yet
- Data will populate as you use the application

---

## Next Steps After Successful Login

1. **Create a Patient**
   - Navigate to Patients section
   - Click "Add Patient"
   - Fill in patient information

2. **Schedule an Appointment**
   - Go to Schedule/Appointments
   - Create appointment for the patient

3. **Test Other Features**
   - Insurance management
   - Treatment planning
   - Billing
   - Reports

---

## Database Verification

To verify the user was created in the database:

```bash
# Connect to Railway PostgreSQL
psql postgresql://postgres:FZHYAmmFYRIFaiZSwiDFJsZLHPtSIWnx@caboose.proxy.rlwy.net:44462/railway

# Query the user
SELECT id, email, role, is_active FROM users WHERE email = 'admin@coredent.com';

# Query the practice
SELECT id, name FROM practices WHERE id = '4463affd-9797-4a2e-9337-4d2b02038716';
```

---

## Environment Configuration Summary

### Backend (.env on Railway)
- `DATABASE_URL`: Connected to Railway PostgreSQL ✅
- `FRONTEND_URL`: https://heartfelt-benevolence-production-ba39.up.railway.app ✅
- `CORS_ORIGINS`: Includes frontend URL ✅
- `DEBUG`: False (production) ✅
- `ENVIRONMENT`: production ✅

### Frontend (.env on Railway)
- `VITE_API_URL`: https://coredentist-production.up.railway.app ✅
- `VITE_APP_NAME`: CoreDent ✅

---

## Troubleshooting Checklist

- [ ] Frontend loads without 404
- [ ] Backend health check returns 200
- [ ] Login page displays correctly
- [ ] No CORS errors in browser console
- [ ] Credentials work (admin@coredent.com / Admin123!)
- [ ] Dashboard loads after login
- [ ] User profile shows correct name
- [ ] No 401/403 errors in network tab

---

## Success Indicators

✅ **All systems operational when:**
1. Frontend loads at https://heartfelt-benevolence-production-ba39.up.railway.app
2. Backend health check returns healthy status
3. Login succeeds with provided credentials
4. Dashboard displays without errors
5. No CORS or authentication errors in console

---

## Important Notes

⚠️ **Security Reminders:**
- Change the admin password after first login
- Don't share credentials in production
- Use strong passwords for all users
- Enable 2FA when available
- Regularly audit user access

---

## Support

If you encounter issues:
1. Check Railway dashboard for service status
2. Review backend logs: Railway → coredentist service → Logs
3. Review frontend logs: Browser console (F12)
4. Verify environment variables are set correctly
5. Check database connectivity with the provided credentials

