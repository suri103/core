# Diagnose Login 403 Issue

## What's Happening
You're getting 403 on `/auth/me` after login. This means the Authorization header is not being sent.

## Root Cause Analysis

### Scenario 1: Old Frontend Build Still Running
- Frontend code hasn't been updated with token storage fix
- Solution: Wait for Railway rebuild to complete

### Scenario 2: Token Not Being Extracted from Login Response
- Login response includes `access_token` but frontend isn't extracting it
- Solution: Check if new code is deployed

### Scenario 3: Token Not Being Sent in Authorization Header
- Token is stored but not being sent in requests
- Solution: Verify API client is calling `setToken()`

## How to Diagnose

### Step 1: Check if New Code is Deployed
Open browser DevTools (F12) → Console tab and run:
```javascript
// Check if the new code is deployed
console.log('Checking for token storage...');
localStorage.getItem('access_token') ? console.log('✅ Token in localStorage') : console.log('❌ No token in localStorage');
```

### Step 2: Check Network Request
1. Open DevTools → Network tab
2. Clear network log
3. Try to login
4. Look for `/auth/login` request
5. Check Response tab - should see `access_token` field
6. Check if `/auth/me` request has `Authorization: Bearer <token>` header

### Step 3: Check Browser Console
Look for any error messages that might indicate:
- Token extraction failed
- API client not initialized
- localStorage access denied

## Expected Behavior After Fix

### Login Request
```
POST /api/v1/auth/login
Response: {
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "...",
  "csrf_token": "...",
  "message": "Login successful"
}
```

### Subsequent Requests
```
GET /api/v1/auth/me
Headers: {
  "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
}
Response: 200 OK with user data
```

## If Still Getting 403

### Option 1: Hard Refresh
- Press Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- This clears cache and reloads page

### Option 2: Clear Cache and Cookies
1. Open DevTools → Application tab
2. Click "Clear site data"
3. Refresh page
4. Try login again

### Option 3: Check Railway Build Status
1. Go to Railway dashboard
2. Check frontend service
3. Look for build status
4. If building, wait for completion
5. If failed, check build logs

## What the Fix Does

The fix ensures:
1. ✅ Login response is parsed correctly
2. ✅ `access_token` is extracted from response
3. ✅ Token is stored in API client via `authApi.setToken()`
4. ✅ Token is persisted in localStorage
5. ✅ Token is restored on page reload
6. ✅ Token is sent in `Authorization: Bearer <token>` header
7. ✅ `/auth/me` receives valid token and returns 200 OK

## Timeline

- Code committed: ✅ Done
- Railway rebuild triggered: ✅ Done
- Waiting for: Frontend build to complete (5-10 minutes typically)
- Then: Test login again

## Next Steps

1. Wait 5-10 minutes for Railway build
2. Hard refresh page (Ctrl+Shift+R)
3. Try login again
4. Check DevTools Network tab for Authorization header
5. Verify `/auth/me` returns 200 OK
