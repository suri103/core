# 🔧 Fix "Failed to Fetch" - CORS Configuration

## Problem
Frontend shows "Failed to fetch" when trying to login because the backend doesn't allow requests from the frontend domain.

## Solution
Add the frontend domain to backend's CORS allowed origins.

## Steps to Fix in Railway Dashboard

### 1. Open Backend Service
- Go to Railway dashboard: https://railway.app
- Click on your **coredentist-production** (backend) service

### 2. Add Environment Variable
- Click on **Variables** tab
- Click **+ New Variable**
- Add this variable:

```
Variable Name: CORS_ORIGINS
Variable Value: https://respectful-strength-production-ef28.up.railway.app,https://coredentist-production.up.railway.app
```

### 3. Redeploy Backend
- After adding the variable, Railway will automatically redeploy
- Wait for deployment to complete (watch the Deployments tab)
- Look for "Build successful" and "Deployment successful"

### 4. Test Login
- Go to: https://respectful-strength-production-ef28.up.railway.app
- Try logging in with:
  - Email: `admin@coredent.com`
  - Password: `Admin123!`

## Alternative: Check Current CORS Setting

If the variable already exists:
1. Go to backend service → Variables tab
2. Find `CORS_ORIGINS` variable
3. Make sure it includes: `https://respectful-strength-production-ef28.up.railway.app`
4. If not, edit it to add the frontend domain
5. Save and wait for automatic redeploy

## What This Does

The CORS (Cross-Origin Resource Sharing) setting tells the backend which domains are allowed to make API requests. Without this, browsers block the requests for security reasons.

## Expected Result

After the backend redeploys with the correct CORS setting:
- Login page will successfully connect to backend
- You'll be able to login with admin credentials
- No more "Failed to fetch" errors

---

**Note**: The backend code already has this configuration in `coredent-api/app/core/config.py`, but it needs to be set as an environment variable in Railway for it to take effect.
