# 🚨 CRITICAL: Clear Build Cache and Redeploy

## The Problem
Railway is using CACHED build layers from the old broken build. The healthcheck is failing because it's running the OLD code, not the NEW fixes.

## The Solution (2 Steps)

### Step 1: Clear Build Cache in Railway

1. Open Railway Dashboard: https://railway.app
2. Go to your project: `practical-dream`
3. Click on the **frontend service** (respectful-strength)
4. Click the **"Settings"** tab
5. Scroll down to **"Danger Zone"**
6. Click **"Clear Build Cache"** button
7. Confirm the action

### Step 2: Redeploy

1. Stay in the frontend service
2. Click the **"Deployments"** tab
3. Click the **"Deploy"** button (top right)
4. Select **"Redeploy"**
5. Wait for the build to complete (will take 2-3 minutes)

## What Will Happen

✅ Railway will rebuild from scratch (no cache)
✅ PWA config will use correct favicon.svg
✅ Healthcheck endpoint will be at top of nginx config
✅ wget will be installed for healthcheck
✅ Container will start successfully
✅ Healthcheck will pass
✅ Frontend will be accessible

## After Deployment

Visit: https://respectful-strength-production-ef28.up.railway.app

You should see the CoreDent login page!

Login with:
- **Email**: admin@coredent.com
- **Password**: Admin123!

---

## If You Still See Errors

Check the Deploy Logs in Railway:
1. Click on the deployment
2. Look for "Build Logs" - should show fresh build (not cached)
3. Look for "Deploy Logs" - should show nginx starting
4. Look for healthcheck passing

If healthcheck still fails, share the full deploy logs.
