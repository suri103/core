# 🔄 Rebuild Frontend with Correct API URL

## Problem
The frontend was built with `localhost:3000` as the API URL instead of the production backend URL. This causes "Failed to fetch" errors.

## Solution
Trigger a rebuild of the frontend in Railway with the correct environment variables.

## Option 1: Force Rebuild in Railway (Easiest)

### Step 1: Update Build Timestamp
In Railway dashboard for your frontend service:
1. Go to **Variables** tab
2. Add or update this variable:
   ```
   VITE_API_BASE_URL=https://coredentist-production.up.railway.app/api/v1
   ```
3. Click **Deploy** or **Redeploy** button

### Step 2: Wait for Build
- Watch the **Deployments** tab
- Wait for "Build successful" message
- Frontend will automatically restart with new build

## Option 2: Trigger Rebuild via Git (Alternative)

If you have the Railway GitHub integration:

1. Make a small change to trigger rebuild:
   ```bash
   cd coredent-style-main
   echo "# $(date)" >> .build-timestamp
   git add .build-timestamp
   git commit -m "Force rebuild with correct API URL"
   git push
   ```

2. Railway will automatically detect the change and rebuild

## Option 3: Manual Redeploy

In Railway dashboard:
1. Go to your frontend service
2. Click on the **Deployments** tab
3. Find the latest deployment
4. Click the three dots menu (⋮)
5. Select **Redeploy**

## Verify the Fix

After rebuild completes:

1. Open: https://respectful-strength-production-ef28.up.railway.app
2. Open browser DevTools (F12)
3. Go to **Console** tab
4. Try to login with:
   - Email: `admin@coredent.com`
   - Password: `Admin123!`
5. Check the **Network** tab - you should see requests going to:
   `https://coredentist-production.up.railway.app/api/v1/auth/login`

## What This Does

Vite (the build tool) bakes environment variables into the JavaScript bundle at build time. If the frontend was built with the wrong API URL, it needs to be rebuilt with the correct one.

The Dockerfile already has the correct URL:
```dockerfile
ENV VITE_API_BASE_URL=https://coredentist-production.up.railway.app/api/v1
```

But Railway needs to rebuild the Docker image for this to take effect.

## Expected Result

After rebuild:
- Login page will connect to the correct backend
- No more "Failed to fetch" errors
- Successful login with admin credentials

---

**Quick Check**: In Railway, verify the `VITE_API_BASE_URL` variable is set correctly in the frontend service Variables tab.
