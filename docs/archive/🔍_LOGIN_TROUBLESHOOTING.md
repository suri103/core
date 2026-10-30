# 🔍 Login Troubleshooting Guide

**Issue**: Login is failing  
**Date**: April 9, 2026

---

## Quick Diagnosis

Run this command to test your backend:

```bash
python diagnose_login.py
```

This will test:
1. ✅ Backend health check
2. ✅ Login endpoint
3. ✅ Token authentication
4. ✅ User data retrieval

---

## Common Issues & Solutions

### Issue 1: "Network Error" or "Cannot connect"

**Symptoms:**
- Login button does nothing
- Console shows network error
- No request in Network tab

**Causes:**
- Backend is down
- Wrong API URL in frontend
- CORS blocking requests

**Solutions:**

1. **Check backend is running:**
   ```bash
   curl https://your-backend.railway.app/health
   ```
   Should return: `{"status":"healthy"}`

2. **Check frontend API URL:**
   - Open `coredent-style-main/.env` or `.env.local`
   - Verify: `VITE_API_BASE_URL=https://your-backend.railway.app/api/v1`
   - NO trailing slash!

3. **Check CORS in Railway:**
   - Go to Railway dashboard
   - Click backend service
   - Variables tab
   - Verify `CORS_ORIGINS` includes your frontend URL

---

### Issue 2: "401 Unauthorized" or "Invalid credentials"

**Symptoms:**
- Login form submits
- Error message: "Invalid credentials"
- Status 401 in Network tab

**Causes:**
- Wrong email/password
- User doesn't exist
- Account is locked
- Password hash mismatch

**Solutions:**

1. **Verify credentials:**
   - Default: `admin@coredent.com` / `Admin123!@#`
   - Check for typos (case-sensitive!)

2. **Check if user exists:**
   ```bash
   python check_railway_database.py
   ```
   Look for your email in the users table

3. **Reset admin password:**
   ```bash
   python update_admin_password_correct.py
   ```
   This will reset to: `Admin123!@#`

4. **Check account lockout:**
   - After 5 failed attempts, account locks for 15 minutes
   - Wait 15 minutes OR reset in database:
   ```sql
   UPDATE users 
   SET failed_login_attempts = 0, 
       locked_until = NULL 
   WHERE email = 'admin@coredent.com';
   ```

---

### Issue 3: "403 Forbidden" or "CSRF token missing"

**Symptoms:**
- Login submits but fails
- Error about CSRF token
- Status 403 in Network tab

**Causes:**
- CSRF token not being sent
- Cookie not being set
- SameSite cookie issue

**Solutions:**

1. **Check cookies in browser:**
   - Open DevTools → Application → Cookies
   - Look for `csrf_token` cookie
   - Should be set after first request

2. **Check SameSite setting:**
   - In `coredent-api/app/api/v1/endpoints/auth.py`
   - Line ~140: `samesite="lax"`
   - Should be "lax" not "none" or "strict"

3. **Clear browser cookies:**
   - DevTools → Application → Clear storage
   - Try login again

---

### Issue 4: Token not being stored/sent

**Symptoms:**
- Login succeeds but immediately logs out
- Subsequent requests fail with 401
- Token not in Authorization header

**Causes:**
- Token not being stored in ApiClient
- Token not being sent in requests
- Token expired immediately

**Solutions:**

1. **Check token storage:**
   - Open browser console
   - After login, check: `window.localStorage` (should be EMPTY - we don't use it)
   - Token should be in memory only (ApiClient)

2. **Check Authorization header:**
   - DevTools → Network tab
   - Click any API request after login
   - Headers section
   - Should see: `Authorization: Bearer eyJ...`

3. **Check token expiration:**
   - In Railway dashboard → Variables
   - `ACCESS_TOKEN_EXPIRE_MINUTES` should be 15 or higher
   - `REFRESH_TOKEN_EXPIRE_DAYS` should be 7 or higher

---

### Issue 5: CORS errors in browser console

**Symptoms:**
- Console shows: "CORS policy blocked"
- Preflight OPTIONS request fails
- Status 0 or CORS error in Network tab

**Causes:**
- Backend CORS not configured
- Wrong origin in CORS_ORIGINS
- Missing CORS headers

**Solutions:**

1. **Check CORS_ORIGINS in Railway:**
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
   ```
   - Must include your frontend URL
   - Separate multiple origins with commas
   - NO trailing slashes!

2. **Check CORS in code:**
   - File: `coredent-api/app/main.py`
   - Should have:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=settings.CORS_ORIGINS,
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

3. **Restart backend after CORS changes:**
   - Railway auto-deploys on git push
   - OR click "Restart" in Railway dashboard

---

## Step-by-Step Debugging

### Step 1: Test Backend Directly

```bash
# Test health
curl https://your-backend.railway.app/health

# Test login
curl -X POST https://your-backend.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@coredent.com","password":"Admin123!@#"}'
```

**Expected response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "csrf_token": "...",
  "message": "Login successful"
}
```

### Step 2: Test Frontend API URL

1. Open browser console
2. Run:
   ```javascript
   console.log(import.meta.env.VITE_API_BASE_URL)
   ```
3. Should show: `https://your-backend.railway.app/api/v1`

### Step 3: Check Network Tab

1. Open DevTools → Network tab
2. Try to login
3. Look for `/auth/login` request
4. Check:
   - Request URL (should be your backend)
   - Request Method (should be POST)
   - Request Headers (Content-Type: application/json)
   - Request Payload (email and password)
   - Response Status (should be 200)
   - Response Body (should have tokens)

### Step 4: Check Console Errors

1. Open DevTools → Console tab
2. Try to login
3. Look for errors:
   - Red errors = something broke
   - CORS errors = backend CORS issue
   - Network errors = backend down or wrong URL
   - 401 errors = wrong credentials
   - 403 errors = CSRF issue

---

## Environment Variables Checklist

### Backend (Railway)

```bash
# Required
DATABASE_URL=postgresql://...  # Auto-set by Railway
SECRET_KEY=your-secret-key-here  # 32+ characters
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173

# Optional but recommended
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
FRONTEND_URL=https://your-frontend.vercel.app
```

### Frontend (Vercel or local)

```bash
# Required
VITE_API_BASE_URL=https://your-backend.railway.app/api/v1

# Optional
VITE_DEV_BYPASS_AUTH=false  # NEVER true in production!
```

---

## Quick Fixes

### Fix 1: Reset Everything

```bash
# 1. Clear browser data
# DevTools → Application → Clear storage → Clear site data

# 2. Reset admin password
python update_admin_password_correct.py

# 3. Restart backend
# Railway dashboard → Click service → Restart

# 4. Try login again
```

### Fix 2: Check Database Connection

```bash
# Run database check
python check_railway_database.py

# Should show:
# - Database connection: OK
# - Users table: EXISTS
# - Admin user: EXISTS
```

### Fix 3: Verify Token Flow

1. Login with correct credentials
2. Check response has `access_token`
3. Check next request has `Authorization: Bearer ...` header
4. If missing, check `coredent-style-main/src/services/api.ts` line ~50

---

## Still Not Working?

### Get Detailed Logs

1. **Backend logs (Railway):**
   - Railway dashboard → Click service
   - "Deployments" tab → Latest deployment
   - Click "View Logs"
   - Look for errors during login

2. **Frontend logs (Browser):**
   - DevTools → Console tab
   - Look for red errors
   - Copy full error message

3. **Network logs:**
   - DevTools → Network tab
   - Filter: "auth"
   - Right-click request → Copy → Copy as cURL
   - Test in terminal

### Common Error Messages

| Error | Meaning | Fix |
|-------|---------|-----|
| "Network error" | Can't reach backend | Check backend URL and CORS |
| "Invalid credentials" | Wrong email/password | Verify credentials or reset |
| "Account locked" | Too many failed attempts | Wait 15 min or reset in DB |
| "CSRF token missing" | CSRF not being sent | Check cookies and headers |
| "Token expired" | Session timed out | Login again |
| "Forbidden" | No permission | Check user role |

---

## Test Credentials

**Default Admin:**
- Email: `admin@coredent.com`
- Password: `Admin123!@#`

**Password Requirements:**
- Minimum 12 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character (!@#$%^&*)

---

## Contact Info

If you're still stuck, provide:

1. Backend URL (Railway)
2. Frontend URL (Vercel or localhost)
3. Error message from console
4. Network tab screenshot
5. Backend logs from Railway

---

## Quick Reference

```bash
# Test backend health
curl https://your-backend.railway.app/health

# Test login
python diagnose_login.py

# Check database
python check_railway_database.py

# Reset admin password
python update_admin_password_correct.py

# View Railway logs
# Go to: https://railway.app → Your project → Backend service → Logs
```

---

**Last Updated**: April 9, 2026  
**Status**: Backend deployed, login should work

