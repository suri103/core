# 🔧 Frontend Service - Restart & Troubleshoot

## Issue
Frontend domain still showing "Not Found" after 10+ minutes. This indicates the service may have crashed or failed to start.

---

## Immediate Action: Restart Frontend Service

### Step 1: Go to Railway Dashboard
1. Open https://railway.app
2. Login to your account
3. Click on **practical-dream** project

### Step 2: Select Frontend Service
1. Click on the **frontend** service (should show in the list)
2. Look at the status indicator:
   - 🟢 Green = Running
   - 🟡 Yellow = Deploying
   - 🔴 Red = Crashed

### Step 3: Check Logs
1. Click the **Logs** tab
2. Look for error messages like:
   - `Docker build failed`
   - `Port already in use`
   - `Nginx configuration error`
   - `Out of memory`
   - `Service crashed`

### Step 4: Restart the Service
1. Click the three dots menu (⋮) in top right
2. Select **Restart**
3. Wait 1-2 minutes for restart
4. Refresh the frontend URL

---

## If Restart Doesn't Work

### Option A: Delete and Redeploy
1. Click the three dots menu (⋮)
2. Select **Delete**
3. Confirm deletion
4. Create new service:
   - Click **+ New**
   - Select **GitHub Repo**
   - Choose your repository
   - Set root directory: `coredent-style-main`
   - Click **Deploy**

### Option B: Check Environment Variables
1. Click **Variables** tab
2. Verify these are set:
   - `VITE_API_URL` = `https://coredentist-production.up.railway.app`
   - `VITE_APP_NAME` = `CoreDent`
3. If missing, add them
4. Restart service

### Option C: Check Dockerfile
1. Verify `coredent-style-main/Dockerfile` exists
2. Check it has multi-stage build:
   - Stage 1: `node:20-alpine` (builder)
   - Stage 2: `nginx:alpine` (runtime)
3. Verify nginx.conf exists

---

## Common Issues & Fixes

### Issue 1: Service Crashed
**Symptoms**: Red status indicator, service won't start  
**Fix**: 
1. Check logs for errors
2. Restart service
3. If still crashes, delete and redeploy

### Issue 2: Build Failed
**Symptoms**: Yellow status, stays deploying  
**Fix**:
1. Check Docker build logs
2. Verify Dockerfile syntax
3. Ensure all dependencies in package.json
4. Redeploy

### Issue 3: Port Configuration
**Symptoms**: Service runs but won't respond  
**Fix**:
1. Verify PORT environment variable (should be 80)
2. Check nginx.conf listens on port 80
3. Restart service

### Issue 4: Out of Memory
**Symptoms**: Service crashes after starting  
**Fix**:
1. Check Railway plan (free tier has limits)
2. Upgrade if needed
3. Optimize build (remove node_modules from Docker)

---

## Verification Steps

After restart, verify:

1. **Service Status**
   - Should show 🟢 Green
   - Status: "Running"

2. **Logs**
   - No error messages
   - Should see nginx starting

3. **Domain**
   - Should be provisioned
   - URL should be accessible

4. **Frontend Access**
   - https://heartfelt-benevolence-production-ba39.up.railway.app
   - Should show login page

---

## If Still Not Working

### Check Backend Connectivity
```bash
# Backend should be working
curl https://coredentist-production.up.railway.app/health

# Should return:
# {"status":"healthy","app":"CoreDent API","version":"1.0.0","environment":"production"}
```

### Check Frontend Build
1. Verify `coredent-style-main/package.json` exists
2. Verify `coredent-style-main/Dockerfile` exists
3. Verify `coredent-style-main/nginx.conf` exists
4. Verify code is on `master` branch

### Check Railway Status
1. Go to https://status.railway.app
2. Check if there are any service outages
3. Check if your region (us-east-4) is affected

---

## Alternative: Use Backend API Directly

While frontend is being fixed, you can test the backend API:

```bash
# Test login
curl -X POST https://coredentist-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@coredent.com",
    "password": "Admin123!"
  }'

# Should return JWT token if credentials are correct
```

---

## Step-by-Step Restart Process

1. Open https://railway.app
2. Go to **practical-dream** project
3. Click **frontend** service
4. Click menu (⋮) → **Restart**
5. Wait 2 minutes
6. Refresh https://heartfelt-benevolence-production-ba39.up.railway.app
7. Should see login page

---

## Expected Timeline After Restart

| Time | Status |
|------|--------|
| 0-30s | Service stopping |
| 30s-1m | Service starting |
| 1-2m | Nginx initializing |
| 2m+ | Should be accessible |

---

## Checklist

- [ ] Opened Railway dashboard
- [ ] Found frontend service
- [ ] Checked service status
- [ ] Reviewed logs for errors
- [ ] Clicked restart
- [ ] Waited 2 minutes
- [ ] Refreshed frontend URL
- [ ] Verified login page loads

---

## Support

If restart doesn't work:
1. Check Railway status page
2. Review deployment logs
3. Verify environment variables
4. Try deleting and redeploying
5. Contact Railway support if infrastructure issue

