# 🚂 Railway Deployment Guide - CoreDent PMS

**Deploy your dental practice management system in 20 minutes**

---

## 📋 Prerequisites

- GitHub account
- Railway account (sign up at railway.app)
- Your code pushed to GitHub

---

## 🚀 STEP 1: Prepare Your Repository (5 minutes)

### 1.1 Create Railway Configuration Files

These files are already created in your repo:
- ✅ `coredent-api/railway.json` - Backend config
- ✅ `coredent-api/Dockerfile` - Already exists
- ✅ `coredent-style-main/railway.json` - Frontend config

### 1.2 Push to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Ready for Railway deployment"

# Create GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/coredent-pms.git
git branch -M main
git push -u origin main
```

---

## 🚀 STEP 2: Deploy Backend API (10 minutes)

### 2.1 Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click "Start a New Project"
3. Select "Deploy from GitHub repo"
4. Choose your `coredent-pms` repository
5. Railway will detect your project

### 2.2 Add PostgreSQL Database

1. In your Railway project dashboard
2. Click "+ New"
3. Select "Database" → "PostgreSQL"
4. Railway will provision a database instantly
5. Note: Database URL is automatically added to your backend service

### 2.3 Configure Backend Service

1. Click on your backend service (coredent-api)
2. Go to "Settings" tab
3. Set "Root Directory" to `coredent-api`
4. Railway will auto-detect Dockerfile

### 2.4 Add Environment Variables

Click "Variables" tab and add these:

```bash
# Application
APP_NAME=CoreDent API
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production

# Database (automatically set by Railway)
# DATABASE_URL=${{Postgres.DATABASE_URL}}

# Security - CHANGE THESE!
SECRET_KEY=your-super-secret-key-min-32-chars-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS - Update with your frontend URL after deployment
CORS_ORIGINS=https://your-frontend.railway.app

# Frontend URL - Update after frontend deployment
FRONTEND_URL=https://your-frontend.railway.app

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100

# HIPAA Compliance
AUDIT_LOG_ENABLED=True
SESSION_TIMEOUT_MINUTES=30
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_LOWERCASE=True
PASSWORD_REQUIRE_DIGIT=True
PASSWORD_REQUIRE_SPECIAL=True
PASSWORD_EXPIRE_DAYS=90

# Email (Optional - configure later)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@coredent.com
SMTP_FROM_NAME=CoreDent PMS

# File Upload
MAX_UPLOAD_SIZE=10485760
ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png,doc,docx

# Pagination
DEFAULT_PAGE_SIZE=10
MAX_PAGE_SIZE=100
```

### 2.5 Deploy Backend

1. Click "Deploy" or wait for auto-deploy
2. Watch the build logs
3. Wait 3-5 minutes for deployment
4. Copy your backend URL (e.g., `https://coredent-api-production.up.railway.app`)

### 2.6 Run Database Migrations

1. Click on your backend service
2. Go to "Settings" → "Deploy"
3. Add "Deploy Command": `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Redeploy

Or use Railway CLI:
```bash
railway run alembic upgrade head
```

### 2.7 Create Admin User

Use Railway CLI:
```bash
railway run python scripts/create_admin.py
```

Or add a one-time job in Railway dashboard.

---

## 🚀 STEP 3: Deploy Frontend (5 minutes)

### 3.1 Create Frontend Service

1. In your Railway project
2. Click "+ New"
3. Select "GitHub Repo"
4. Choose the same repository
5. Railway will create a new service

### 3.2 Configure Frontend Service

1. Click on the new service
2. Go to "Settings"
3. Set "Root Directory" to `coredent-style-main`
4. Set "Build Command": `npm install && npm run build`
5. Set "Start Command": `npm run preview -- --host 0.0.0.0 --port $PORT`

### 3.3 Add Frontend Environment Variables

Click "Variables" tab:

```bash
# API Configuration - Use your backend URL from Step 2.5
VITE_API_BASE_URL=https://coredent-api-production.up.railway.app/api/v1

# Feature Flags
VITE_ENABLE_DEMO_MODE=false
VITE_DEV_BYPASS_AUTH=false

# Analytics (Optional)
VITE_ANALYTICS_ENABLED=false
VITE_POSTHOG_KEY=
VITE_POSTHOG_HOST=https://app.posthog.com

# Error Monitoring (Optional)
VITE_SENTRY_DSN=
VITE_SENTRY_ENVIRONMENT=production

# Development
VITE_DEBUG=false
VITE_ENABLE_DEVTOOLS=false
```

### 3.4 Deploy Frontend

1. Click "Deploy"
2. Wait 2-3 minutes
3. Copy your frontend URL (e.g., `https://coredent-frontend-production.up.railway.app`)

---

## 🚀 STEP 4: Update CORS Settings (2 minutes)

### 4.1 Update Backend Environment Variables

1. Go back to your backend service
2. Click "Variables"
3. Update these variables with your actual frontend URL:

```bash
CORS_ORIGINS=https://coredent-frontend-production.up.railway.app
FRONTEND_URL=https://coredent-frontend-production.up.railway.app
```

4. Save and redeploy

---

## ✅ STEP 5: Verify Deployment (3 minutes)

### 5.1 Test Backend

```bash
# Health check
curl https://your-backend-url.railway.app/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}
```

### 5.2 Test Frontend

1. Open your frontend URL in browser
2. You should see the login page
3. Try logging in with admin credentials

### 5.3 Test Full Flow

1. Login with admin account
2. Create a test patient
3. Create a test appointment
4. Verify data persists after refresh

---

## 🎯 STEP 6: Custom Domain (Optional)

### 6.1 Add Custom Domain to Frontend

1. Go to frontend service → "Settings" → "Domains"
2. Click "Add Domain"
3. Enter your domain (e.g., `app.coredent.com`)
4. Add CNAME record to your DNS:
   - Name: `app`
   - Value: `your-frontend.railway.app`

### 6.2 Add Custom Domain to Backend

1. Go to backend service → "Settings" → "Domains"
2. Click "Add Domain"
3. Enter your API domain (e.g., `api.coredent.com`)
4. Add CNAME record to your DNS:
   - Name: `api`
   - Value: `your-backend.railway.app`

### 6.3 Update Environment Variables

Update CORS and Frontend URL with your custom domains.

---

## 📊 Monitoring & Maintenance

### View Logs

1. Click on any service
2. Go to "Deployments" tab
3. Click on latest deployment
4. View real-time logs

### Monitor Metrics

1. Click on service
2. Go to "Metrics" tab
3. View CPU, Memory, Network usage

### Database Backups

Railway automatically backs up your PostgreSQL database daily.

To create manual backup:
1. Click on PostgreSQL service
2. Go to "Data" tab
3. Click "Backup"

---

## 💰 Cost Estimation

### Railway Pricing

- **Starter Plan**: $5/month credit (free tier)
- **Usage-based**: $0.000231 per GB-second
- **Typical cost**: $20-30/month for small practice

### What You Get

- Backend API (FastAPI)
- PostgreSQL Database (with backups)
- Frontend (React)
- SSL certificates (automatic)
- Custom domains
- Automatic deployments

---

## 🔧 Troubleshooting

### Backend won't start

**Check logs for:**
- Database connection errors → Verify DATABASE_URL
- Missing environment variables → Add all required vars
- Port binding issues → Railway sets PORT automatically

### Frontend can't connect to backend

**Check:**
- VITE_API_BASE_URL is correct
- CORS_ORIGINS includes frontend URL
- Backend is running (check health endpoint)

### Database migration failed

**Run manually:**
```bash
railway run alembic upgrade head
```

### 502 Bad Gateway

**Usually means:**
- Backend is still starting (wait 30 seconds)
- Backend crashed (check logs)
- Database not connected

---

## 🚀 Next Steps After Deployment

1. ✅ Test all features thoroughly
2. ✅ Create your first real practice
3. ✅ Invite staff members
4. ✅ Configure email settings (SMTP)
5. ✅ Set up monitoring alerts
6. ✅ Add custom domain
7. ✅ Start onboarding customers at $499/month!

---

## 📞 Support

### Railway Support
- Discord: [railway.app/discord](https://railway.app/discord)
- Docs: [docs.railway.app](https://docs.railway.app)
- Status: [status.railway.app](https://status.railway.app)

### CoreDent Issues
- Check logs in Railway dashboard
- Review error messages
- Test locally with same environment variables

---

## 🎉 Congratulations!

Your CoreDent PMS is now live on Railway!

**Your URLs:**
- Frontend: `https://your-frontend.railway.app`
- Backend: `https://your-backend.railway.app`
- Database: Managed by Railway

**Monthly Cost:** ~$20-30
**Revenue Potential:** $499/month per practice
**Profit Margin:** 85%+

**Start onboarding your first dental practice today!**

---

**Deployment Date:** March 21, 2026  
**Platform:** Railway  
**Status:** ✅ PRODUCTION READY  
**Time to Deploy:** 20 minutes  
**Time to First Customer:** Today!
