# 🚀 Deploy Frontend to Railway - Step by Step

## Backend Status: ✅ LIVE AND HEALTHY

Backend URL: `https://coredentist-production.up.railway.app`

## Deploy Frontend (10 Minutes)

### Step 1: Create New Railway Service

1. Go to Railway dashboard: https://railway.app/project/practical-dream
2. Click "+ New" button (top right)
3. Select "GitHub Repo"
4. Select your repository: `suraiamkapooram10008-lgtm/coredentist`
5. Click "Add Service"

### Step 2: Configure Build Settings

After creating the service, configure it:

1. Click on the new service
2. Go to "Settings" tab
3. Set these values:

**Root Directory:**
```
coredent-style-main
```

**Build Command:** (leave default or set to)
```
npm run build
```

**Start Command:** (leave default, Dockerfile will handle it)
```
(empty - uses Dockerfile)
```

### Step 3: Add Environment Variables

Click "Variables" tab and add:

**Required Variables:**
```
VITE_API_URL=https://coredentist-production.up.railway.app
NODE_ENV=production
```

**Optional (for analytics/monitoring):**
```
VITE_ENABLE_ANALYTICS=false
VITE_SENTRY_DSN=
```

### Step 4: Deploy

1. Click "Deploy" or wait for auto-deploy
2. Railway will:
   - Build the Docker image
   - Run `npm install`
   - Run `npm run build`
   - Start nginx server
   - Expose on Railway domain

### Step 5: Get Frontend URL

After deployment completes:
1. Go to "Settings" tab
2. Scroll to "Domains" section
3. Click "Generate Domain"
4. Copy the generated URL (e.g., `coredentist-frontend.up.railway.app`)

### Step 6: Update Backend CORS

Now update the backend to allow requests from frontend:

1. Go back to `coredentist` (backend) service
2. Click "Variables" tab
3. Update `CORS_ORIGINS` to:
```
["https://coredentist-frontend.up.railway.app"]
```
(Replace with your actual frontend URL)

4. Backend will auto-redeploy

### Step 7: Test Full Application

Open your frontend URL and test:
- ✅ Login page loads
- ✅ Can register new user
- ✅ Can login
- ✅ Dashboard loads
- ✅ Can view patients
- ✅ Can create appointments
- ✅ All features work

## Alternative: Use Railway CLI

If you prefer command line:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link practical-dream

# Deploy frontend
cd coredent-style-main
railway up
```

## Troubleshooting

**If frontend doesn't connect to backend:**
1. Check VITE_API_URL is correct
2. Check CORS_ORIGINS includes frontend URL
3. Check browser console for errors
4. Verify backend is still healthy

**If build fails:**
1. Check Railway logs for errors
2. Verify Dockerfile exists in coredent-style-main/
3. Check package.json has correct scripts
4. Verify all dependencies are in package.json

## Expected Timeline

- **Step 1-3:** 5 minutes (configuration)
- **Step 4:** 5-10 minutes (build and deploy)
- **Step 5-6:** 2 minutes (CORS update)
- **Step 7:** 5 minutes (testing)

**Total:** ~20 minutes

## What Happens Next

Once frontend is deployed:
1. You'll have two Railway services:
   - Backend: `coredentist-production.up.railway.app`
   - Frontend: `coredentist-frontend.up.railway.app`
2. Both will auto-deploy on git push
3. You can add custom domains later
4. Monitor both services in Railway dashboard

## Current Status

✅ Backend deployed and healthy
✅ Database connected and migrated
✅ API endpoints working
🔄 Frontend deployment (next step)
⏳ Full application testing
⏳ Production launch

---

**Next Action:** Create new Railway service for frontend (Step 1 above)
