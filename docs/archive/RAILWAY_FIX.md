# 🚂 Railway Deployment Fix

Railway couldn't detect the project type because you have a monorepo with two separate apps.

## ✅ What I Fixed

Created a root-level `Dockerfile` that tells Railway:
1. Use Python 3.13
2. Copy the backend code from `coredent-api/`
3. Install dependencies
4. Run migrations
5. Start the FastAPI server

---

## 🚀 Deploy Backend to Railway (Updated Steps)

### Step 1: Go to Railway
1. Open https://railway.app
2. Sign in with GitHub
3. Click "Start a New Project"
4. Select "Deploy from GitHub repo"
5. Choose: `suraiamkapooram10008-lgtm/coredentist`

### Step 2: Railway Auto-Detects Dockerfile
- Railway will now see the root `Dockerfile`
- It will automatically use it to build your backend

### Step 3: Add PostgreSQL Database
1. Click "+ New" in your project
2. Select "Database" → "PostgreSQL"
3. Done!

### Step 4: Add Environment Variables
Click "Variables" and add:

```bash
SECRET_KEY=your-super-secret-key-min-32-chars-change-this
DEBUG=False
ENVIRONMENT=production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=https://your-frontend.railway.app
FRONTEND_URL=https://your-frontend.railway.app
RATE_LIMIT_PER_MINUTE=100
AUDIT_LOG_ENABLED=True
SESSION_TIMEOUT_MINUTES=30
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_LOWERCASE=True
PASSWORD_REQUIRE_DIGIT=True
PASSWORD_REQUIRE_SPECIAL=True
```

### Step 5: Deploy
- Click "Deploy"
- Wait 3-5 minutes
- ✅ Backend is live!

---

## 🎨 Deploy Frontend to Railway (Separate Service)

### Step 1: Add New Service
1. In your Railway project, click "+ New"
2. Select "GitHub Repo"
3. Choose the same repository

### Step 2: Configure Frontend Service
1. Click on the new service
2. Go to "Settings"
3. Set "Root Directory" to `coredent-style-main`
4. Set "Build Command": `npm install && npm run build`
5. Set "Start Command": `npm run preview -- --host 0.0.0.0 --port $PORT`

### Step 3: Add Environment Variables
```bash
VITE_API_BASE_URL=https://your-backend.railway.app/api/v1
VITE_ENABLE_DEMO_MODE=false
VITE_DEV_BYPASS_AUTH=false
VITE_DEBUG=false
```

### Step 4: Deploy
- Click "Deploy"
- Wait 2-3 minutes
- ✅ Frontend is live!

---

## 📝 What Changed

**Before:** Railway couldn't detect project type (monorepo issue)

**After:** 
- Root `Dockerfile` tells Railway how to build backend
- Frontend deployed as separate service with custom build commands
- Both services share the same PostgreSQL database

---

## 🎯 Next Steps

1. **Commit the fix:**
```bash
git add Dockerfile RAILWAY_FIX.md
git commit -m "Add root Dockerfile for Railway backend deployment"
git push origin fix/readme-update
```

2. **Deploy to Railway:**
   - Go to https://railway.app
   - Create new project from GitHub
   - Select your repository
   - Railway will now detect the Dockerfile automatically

3. **Test deployment:**
   - Backend: `https://your-backend.railway.app/health`
   - Frontend: `https://your-frontend.railway.app`

---

## 🆘 If You Still Get Errors

**Error: "Railpack could not determine how to build the app"**

**Solution:**
1. Go to Railway dashboard
2. Click on your service
3. Go to "Settings"
4. Scroll to "Build"
5. Select "Dockerfile" as builder
6. Set Dockerfile path to `./Dockerfile`
7. Redeploy

---

## ✅ You're Ready!

Your backend is now configured for Railway deployment. The root `Dockerfile` will be automatically detected and used.

**Next:** Push the changes and deploy to Railway!
