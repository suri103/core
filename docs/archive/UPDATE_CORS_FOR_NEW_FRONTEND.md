# 🔧 Update CORS Configuration for New Frontend URL

## Issue
Frontend URL changed from:
- ❌ `heartfelt-benevolence-production-ba39.up.railway.app`

To:
- ✅ `determined-nurturing-production-2704.up.railway.app`

Backend CORS needs to be updated to allow requests from the new frontend URL.

---

## Solution: Update CORS_ORIGINS Environment Variable

### Step 1: Go to Railway Dashboard
1. Open https://railway.app
2. Go to **practical-dream** project
3. Click on **coredentist** (backend service)

### Step 2: Update Environment Variables
1. Click **Variables** tab
2. Find `CORS_ORIGINS` variable
3. Update the value to include the new frontend URL:

**Old Value:**
```
https://heartfelt-benevolence-production-ba39.up.railway.app
```

**New Value:**
```
https://determined-nurturing-production-2704.up.railway.app
```

Or if you want to keep both (for backward compatibility):
```
https://heartfelt-benevolence-production-ba39.up.railway.app,https://determined-nurturing-production-2704.up.railway.app
```

### Step 3: Save and Restart
1. Click **Save** (or it auto-saves)
2. Click the three dots menu (⋮)
3. Select **Restart**
4. Wait 1-2 minutes for restart

---

## Verification

### Test CORS Headers
After restart, test that CORS is working:

```bash
# Test CORS preflight request
curl -X OPTIONS https://coredentist-production.up.railway.app/api/v1/auth/login \
  -H "Origin: https://determined-nurturing-production-2704.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Should see response headers:
# Access-Control-Allow-Origin: https://determined-nurturing-production-2704.up.railway.app
# Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH
# Access-Control-Allow-Headers: Content-Type, Authorization, X-CSRF-Token, X-Requested-With
```

### Test Frontend Login
1. Open https://determined-nurturing-production-2704.up.railway.app
2. Try to login with:
   - Email: `admin@coredent.com`
   - Password: `Admin123!`
3. Should NOT see CORS errors in browser console

---

## Current Environment Variables

### Backend (coredentist service)

| Variable | Current Value | Notes |
|----------|---------------|-------|
| `DATABASE_URL` | `postgresql://...` | ✅ Set |
| `SECRET_KEY` | `***` | ✅ Set |
| `ENVIRONMENT` | `production` | ✅ Set |
| `DEBUG` | `False` | ✅ Set |
| `FRONTEND_URL` | `https://heartfelt-benevolence-production-ba39.up.railway.app` | ⚠️ Should update |
| `CORS_ORIGINS` | `https://heartfelt-benevolence-production-ba39.up.railway.app` | ⚠️ **NEEDS UPDATE** |
| `ALLOWED_HOSTS` | `coredentist-production.up.railway.app,localhost` | ✅ Set |
| `PORT` | `8000` | ✅ Set |

---

## What to Update

### Option 1: Update CORS_ORIGINS Only (Minimum)
```
CORS_ORIGINS = https://determined-nurturing-production-2704.up.railway.app
```

### Option 2: Update Both CORS_ORIGINS and FRONTEND_URL (Recommended)
```
CORS_ORIGINS = https://determined-nurturing-production-2704.up.railway.app
FRONTEND_URL = https://determined-nurturing-production-2704.up.railway.app
```

### Option 3: Keep Both URLs (For Backward Compatibility)
```
CORS_ORIGINS = https://heartfelt-benevolence-production-ba39.up.railway.app,https://determined-nurturing-production-2704.up.railway.app
FRONTEND_URL = https://determined-nurturing-production-2704.up.railway.app
```

---

## Step-by-Step Instructions

### 1. Open Railway Dashboard
```
https://railway.app
```

### 2. Navigate to Backend Service
- Project: **practical-dream**
- Service: **coredentist** (backend)

### 3. Click Variables Tab
- Look for `CORS_ORIGINS`
- Look for `FRONTEND_URL`

### 4. Update Values
- Change `CORS_ORIGINS` to new frontend URL
- Optionally update `FRONTEND_URL` to new frontend URL

### 5. Restart Service
- Click menu (⋮)
- Select **Restart**
- Wait 1-2 minutes

### 6. Test
- Open new frontend URL
- Try to login
- Check browser console for CORS errors

---

## Important Notes

⚠️ **Do NOT include `http://` or `https://` twice**
- ✅ Correct: `https://determined-nurturing-production-2704.up.railway.app`
- ❌ Wrong: `https://https://determined-nurturing-production-2704.up.railway.app`

⚠️ **Do NOT include trailing slashes**
- ✅ Correct: `https://determined-nurturing-production-2704.up.railway.app`
- ❌ Wrong: `https://determined-nurturing-production-2704.up.railway.app/`

⚠️ **Multiple URLs must be comma-separated**
- ✅ Correct: `https://url1.com,https://url2.com`
- ❌ Wrong: `https://url1.com; https://url2.com`

---

## After Update

### Expected Behavior
1. Frontend loads at new URL
2. Login page displays
3. No CORS errors in console
4. Login request succeeds
5. Dashboard loads

### If CORS Errors Still Appear
1. Check that CORS_ORIGINS was updated correctly
2. Verify backend service restarted
3. Clear browser cache (Ctrl+Shift+Delete)
4. Try incognito/private window
5. Check backend logs for errors

---

## Database Changes Needed?

**No database changes needed!**

- PostgreSQL doesn't need updates
- CORS is a backend configuration only
- Database connection string stays the same
- Test user credentials stay the same

---

## Rollback (If Needed)

If you need to revert to the old frontend URL:

1. Go to Railway dashboard
2. Click **coredentist** service
3. Click **Variables** tab
4. Change `CORS_ORIGINS` back to old URL
5. Restart service

---

## Summary

| Action | Required | Notes |
|--------|----------|-------|
| Update CORS_ORIGINS | ✅ Yes | Change to new frontend URL |
| Update FRONTEND_URL | ⚠️ Optional | Recommended for consistency |
| Update Database | ❌ No | No changes needed |
| Restart Backend | ✅ Yes | Required for changes to take effect |
| Update Frontend | ❌ No | Already deployed at new URL |

---

## Quick Checklist

- [ ] Opened Railway dashboard
- [ ] Navigated to coredentist service
- [ ] Clicked Variables tab
- [ ] Found CORS_ORIGINS variable
- [ ] Updated to new frontend URL
- [ ] Clicked Save
- [ ] Restarted service
- [ ] Waited 1-2 minutes
- [ ] Tested frontend login
- [ ] No CORS errors in console

