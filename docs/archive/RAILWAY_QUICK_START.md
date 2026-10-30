# 🚂 Railway Quick Start - 20 Minute Deployment

Deploy CoreDent PMS to production in 20 minutes.

---

## ⚡ Super Quick Version

```bash
# 1. Push to GitHub (if not already)
git push origin main

# 2. Go to railway.app
# 3. Click "Start a New Project" → "Deploy from GitHub"
# 4. Select your repo
# 5. Add PostgreSQL database (click "+ New" → "Database" → "PostgreSQL")
# 6. Configure environment variables (see below)
# 7. Deploy!
```

---

## 🔑 Required Environment Variables

### Backend (coredent-api)

**Copy these to Railway Variables tab:**

```bash
# Security - CHANGE THIS!
SECRET_KEY=change-this-to-a-random-32-char-string-in-production

# CORS - Update after frontend deployment
CORS_ORIGINS=https://your-frontend.railway.app
FRONTEND_URL=https://your-frontend.railway.app

# Everything else can use defaults
DEBUG=False
ENVIRONMENT=production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
RATE_LIMIT_PER_MINUTE=100
AUDIT_LOG_ENABLED=True
SESSION_TIMEOUT_MINUTES=30
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_LOWERCASE=True
PASSWORD_REQUIRE_DIGIT=True
PASSWORD_REQUIRE_SPECIAL=True
```

### Frontend (coredent-style-main)

**Copy these to Railway Variables tab:**

```bash
# API URL - Update with your backend URL
VITE_API_BASE_URL=https://your-backend.railway.app/api/v1

# Disable dev features
VITE_ENABLE_DEMO_MODE=false
VITE_DEV_BYPASS_AUTH=false
VITE_DEBUG=false
```

---

## 📝 Step-by-Step Checklist

### ✅ Backend Deployment

- [ ] Create Railway project from GitHub
- [ ] Add PostgreSQL database
- [ ] Set root directory to `coredent-api`
- [ ] Add environment variables
- [ ] Deploy (wait 3-5 min)
- [ ] Copy backend URL
- [ ] Run migrations: `railway run alembic upgrade head`
- [ ] Create admin: `railway run python scripts/create_admin.py`

### ✅ Frontend Deployment

- [ ] Add new service to same Railway project
- [ ] Set root directory to `coredent-style-main`
- [ ] Add environment variables (use backend URL)
- [ ] Deploy (wait 2-3 min)
- [ ] Copy frontend URL

### ✅ Final Configuration

- [ ] Update backend CORS_ORIGINS with frontend URL
- [ ] Update backend FRONTEND_URL with frontend URL
- [ ] Redeploy backend
- [ ] Test login at frontend URL
- [ ] Create test patient
- [ ] Verify everything works

---

## 🧪 Testing Your Deployment

### 1. Test Backend Health

```bash
curl https://your-backend.railway.app/health
```

Expected: `{"status":"healthy","version":"1.0.0"}`

### 2. Test Frontend

Open `https://your-frontend.railway.app` in browser.

You should see the login page.

### 3. Test Login

Use the admin credentials you created.

### 4. Test Full Flow

1. Login
2. Create a patient
3. Create an appointment
4. Refresh page
5. Verify data persists

---

## 💰 Cost

**Expected monthly cost:** $20-30

**What you get:**
- Backend API (FastAPI)
- PostgreSQL database with backups
- Frontend (React)
- SSL certificates
- Automatic deployments
- 99.9% uptime

**Revenue per practice:** $499/month

**Profit margin:** 85%+

---

## 🆘 Common Issues

### "Database connection failed"

**Fix:** Railway automatically sets DATABASE_URL. Just wait 30 seconds for database to be ready.

### "CORS error in browser"

**Fix:** Update CORS_ORIGINS in backend with your frontend URL.

### "502 Bad Gateway"

**Fix:** Backend is still starting. Wait 30 seconds and refresh.

### "Migrations not running"

**Fix:** Run manually:
```bash
railway run alembic upgrade head
```

---

## 🎯 After Deployment

1. **Test everything** - Click through all features
2. **Set up email** - Add SMTP credentials for password resets
3. **Add custom domain** - Use your own domain (optional)
4. **Create first practice** - Set up your first customer
5. **Start selling** - Onboard practices at $499/month!

---

## 📚 Full Documentation

See `RAILWAY_DEPLOYMENT_GUIDE.md` for detailed instructions.

---

## 🎉 You're Live!

Your dental practice management system is now running in production!

**Time to first customer:** Today  
**Monthly revenue potential:** $499 × number of practices  
**Infrastructure cost:** ~$25/month  

**Start onboarding dental practices now!**
