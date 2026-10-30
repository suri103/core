# 🔧 Frontend Crash - Complete Fix

## Problem
Frontend nginx starts but application doesn't respond. This means:
- Docker build succeeded
- Nginx started
- But the built assets aren't being served properly

## Root Causes
1. Build failed silently (dist folder empty)
2. Environment variables not available during build
3. Nginx can't find the dist folder

## Solution: Delete & Redeploy Frontend

### Step 1: Delete Current Frontend Service
1. Go to: https://railway.app
2. Project: **practical-dream**
3. Click: **frontend** service
4. Click menu (⋮) in top right
5. Select: **Delete**
6. Confirm deletion

### Step 2: Create New Frontend Service
1. Click: **+ New**
2. Select: **GitHub Repo**
3. Choose your repository
4. Set **Root Directory**: `coredent-style-main`
5. Click: **Deploy**

### Step 3: Add Environment Variables (BEFORE it builds)
1. Wait for service to appear in the list
2. Click the **frontend** service
3. Click: **Variables** tab
4. Add Variable 1:
   - Name: `VITE_API_URL`
   - Value: `https://coredentist-production.up.railway.app`
5. Add Variable 2:
   - Name: `VITE_APP_NAME`
   - Value: `CoreDent`
6. Click **Save**

### Step 4: Wait for Build & Deployment
- Watch the deployment progress
- Should take 3-5 minutes
- Look for "Deployment successful" message

### Step 5: Test
1. Open: https://determined-nurturing-production-2704.up.railway.app (or new URL if different)
2. Should see login page
3. No errors in console (F12)

---

## Alternative: Check Build Logs

If you want to see what went wrong before deleting:

1. Go to Railway dashboard
2. Click **frontend** service
3. Click **Logs** tab
4. Look for error messages like:
   - `npm ERR!` - build failed
   - `ENOENT` - file not found
   - `Cannot find module` - missing dependency

---

## Why This Happens

Frontend needs environment variables during build time (Vite build):
- `VITE_API_URL` - used in the build to configure API endpoint
- `VITE_APP_NAME` - used in the build to set app name

Without these, the build might fail or create an incomplete dist folder.

---

## Quick Checklist

- [ ] Deleted old frontend service
- [ ] Created new frontend service
- [ ] Set root directory to `coredent-style-main`
- [ ] Added VITE_API_URL variable
- [ ] Added VITE_APP_NAME variable
- [ ] Waited for deployment to complete
- [ ] Tested frontend loads
- [ ] No errors in console

---

## Expected Timeline

| Step | Time | Status |
|------|------|--------|
| Delete service | 1 min | Quick |
| Create service | 1 min | Quick |
| Add variables | 1 min | Quick |
| Build & deploy | 3-5 min | Wait |
| Test | 1 min | Verify |
| **Total** | **~10 min** | **Complete** |

---

## If Still Not Working

### Check Build Logs
1. Go to Railway dashboard
2. Click **frontend** service
3. Click **Logs** tab
4. Look for errors

### Common Build Errors

**Error: Cannot find module**
- Missing dependency in package.json
- Run `npm install` locally to verify

**Error: VITE_API_URL is undefined**
- Variable not set before build
- Add variable and redeploy

**Error: Port already in use**
- Nginx config issue
- Check nginx.conf listens on port 80

### If Build Logs Show No Errors
1. Check if dist folder was created
2. Verify nginx.conf is correct
3. Try restarting the service
4. Check Railway status page for outages

---

## Backend Status (Should Still Be Working)

✅ Backend: https://coredentist-production.up.railway.app  
✅ Health: https://coredentist-production.up.railway.app/health  
✅ Database: Connected  
✅ Test User: Created  

---

## Test Credentials (Still Valid)

```
Email:    admin@coredent.com
Password: Admin123!
```

---

## Next Steps After Frontend Works

1. Test login
2. Verify dashboard loads
3. Check for CORS errors
4. Test API connectivity
5. Create additional users

