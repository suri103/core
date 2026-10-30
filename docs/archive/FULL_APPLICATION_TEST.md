# Full Application Testing Guide

## Current Deployment Status

| Service | URL | Status |
|---------|-----|--------|
| Backend API | https://coredentist-production.up.railway.app | ✅ Running |
| Frontend | https://heartfelt-benevolence-production-ba39.up.railway.app | ✅ Running |
| Database | PostgreSQL (Railway) | ✅ Connected |

## Pre-Testing Checklist

Before testing, make sure:
- [ ] Backend CORS_ORIGINS has been updated with frontend URL
- [ ] Backend service has restarted (wait 30-60 seconds)
- [ ] Backend health check passes: https://coredentist-production.up.railway.app/health
- [ ] Frontend loads without errors

## Test 1: Frontend Loads

1. Open: https://heartfelt-benevolence-production-ba39.up.railway.app
2. Expected: Login page loads
3. Check browser console (F12) for any errors
4. If you see red errors, note them down

## Test 2: Backend Health Check

1. Open: https://coredentist-production.up.railway.app/health
2. Expected response:
   ```json
   {
     "status": "healthy",
     "app": "CoreDent API",
     "version": "1.0.0",
     "environment": "production"
   }
   ```

## Test 3: Login Flow

1. Go to frontend: https://heartfelt-benevolence-production-ba39.up.railway.app
2. Try to login with test credentials
3. Open browser console (F12 → Network tab)
4. Look for API calls to the backend
5. Check for any CORS errors (red errors in console)

### Expected Behavior:
- Login form submits
- API call goes to backend
- User is authenticated
- Redirected to dashboard

### If CORS Error Appears:
- Error message: "Access to XMLHttpRequest at 'https://coredentist-production...' from origin 'https://heartfelt-benevolence...' has been blocked by CORS policy"
- Solution: Go back to Railway and verify CORS_ORIGINS is set correctly

## Test 4: API Functionality

Once logged in, test these features:

### Patients
1. Go to Patients page
2. Try to view patient list
3. Check Network tab for API calls
4. Verify data loads

### Appointments
1. Go to Appointments page
2. Try to view appointments
3. Verify data loads

### Other Pages
- Dashboard
- Schedule
- Billing
- Insurance
- Reports

## Test 5: Check Browser Console

Open Developer Tools (F12) and check:

### Console Tab
- Should have NO red errors
- May have yellow warnings (OK)
- Look for CORS errors specifically

### Network Tab
- API calls should return 200 status
- Look for failed requests (red)
- Check response headers for CORS headers

### Application Tab
- Check localStorage for auth token
- Check cookies

## Common Issues and Solutions

### Issue: "Cannot GET /api/..."
- **Cause**: Backend not responding
- **Solution**: Check backend health endpoint, verify CORS_ORIGINS

### Issue: CORS Error in Console
- **Cause**: Frontend URL not in CORS_ORIGINS
- **Solution**: Update CORS_ORIGINS in Railway backend variables

### Issue: Login fails silently
- **Cause**: API error or network issue
- **Solution**: Check Network tab in browser console, look for failed requests

### Issue: Page loads but no data
- **Cause**: API calls failing
- **Solution**: Check Network tab, look for 401/403/500 errors

## Performance Check

1. Open frontend
2. Open DevTools (F12)
3. Go to Performance tab
4. Reload page
5. Check load time (should be < 3 seconds)

## Security Check

1. Open frontend
2. Check that URL is HTTPS (not HTTP)
3. Check that backend URL is HTTPS
4. Look for security warnings in console

## Final Verification

If all tests pass:
- ✅ Frontend loads
- ✅ Backend responds
- ✅ Login works
- ✅ API calls succeed
- ✅ No CORS errors
- ✅ Data displays correctly

Then the application is ready for use!

## Next Steps

If everything works:
1. Create test user accounts
2. Test all features thoroughly
3. Monitor logs for errors
4. Set up monitoring/alerts

If something fails:
1. Check the specific error message
2. Review the troubleshooting section
3. Check Railway logs for backend errors
4. Check browser console for frontend errors
