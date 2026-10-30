# 🚨 FIX RAILWAY CORS ERROR

## Problem
Your frontend at `https://respectful-strength-production-ef28.up.railway.app` cannot access the backend at `https://coredentist-production.up.railway.app` due to CORS policy.

## Root Cause
The backend's `CORS_ORIGINS` environment variable doesn't include the frontend's Railway domain.

## Solution: Update Railway Environment Variables

### Step 1: Open Railway Dashboard
1. Go to https://railway.app
2. Login to your account
3. Select your project

### Step 2: Update Backend Environment Variables
1. Click on the **backend service** (coredentist-production)
2. Go to the **Variables** tab
3. Find `CORS_ORIGINS` (or add it if missing)
4. Set the value to:
   ```
   https://respectful-strength-production-ef28.up.railway.app,https://coredentist-production.up.railway.app
   ```

### Step 3: Also Update These Variables
While you're there, make sure these are also set:

- `FRONTEND_URL`: `https://respectful-strength-production-ef28.up.railway.app`
- `ALLOWED_HOSTS`: `coredentist-production.up.railway.app`

### Step 4: Deploy
1. Click **"Deploy"** or the backend will auto-redeploy
2. Wait for deployment to complete (1-2 minutes)

### Step 5: Test
1. Go to `https://respectful-strength-production-ef28.up.railway.app`
2. Try logging in with:
   - Email: `admin@coredent.com`
   - Password: `Admin123!@#`

## Why This Happened
Railway generates random subdomain names for deployments. Your frontend got a new domain (`respectful-strength-production-ef28`), but the backend still only allows the old domain in CORS.

## Quick Check
After updating, you can verify the backend is working:
```bash
curl https://coredentist-production.up.railway.app/health
```

Should return:
```json
{"status":"healthy","database":"connected"}
```

## If You're Testing Locally Instead
If you want to test locally (not Railway), use:
1. Backend: `cd coredent-api && uvicorn app.main:app --host 0.0.0.0 --port 8080`
2. Frontend: `cd coredent-style-main && npm run dev` (will use port 5173)
3. Access: `http://localhost:5173`

The local `.env` files are already configured correctly for local development.
