# 🚀 Next Steps - Launch CoreDent PMS

Your backend is **100% complete**. Here's what you need to do to launch:

---

## 🎯 Quick Launch (20 minutes total)

### Step 1: Setup Railway Account (3 min)
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project"

---

### Step 2: Add PostgreSQL Database (2 min)
1. In Railway dashboard, click "New Service"
2. Select "Database" → "PostgreSQL"
3. Railway creates database automatically
4. Click on PostgreSQL service → "Variables" tab
5. Copy `DATABASE_URL` (Railway provides this)

---

### Step 3: Add Backend Service (5 min)
1. In same Railway project, click "New Service"
2. Select "GitHub Repo"
3. Connect your `coredent-api` repository
4. Railway auto-detects FastAPI

**Set Environment Variables:**
In Railway dashboard → Backend Service → Variables, add:
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
SECRET_KEY=[generate a secure key - use: openssl rand -hex 32]
DEBUG=False
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend-domain.com
FRONTEND_URL=https://your-frontend-domain.com
```

**Set Start Command:**
In Railway dashboard → Backend Service → Settings:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### Step 4: Deploy Backend (1 min)
1. Railway auto-deploys when you push to GitHub
2. Wait for deployment to complete
3. Your API is live at: `https://[project-name].up.railway.app`
4. Test: Open `https://[project-name].up.railway.app/docs`

---

### Step 5: Run Database Migration (2 min)
In Railway dashboard → Backend Service → Settings → Shell:
```bash
alembic upgrade head
```

Or add to start command:
```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### Step 6: Create Admin User (1 min)
In Railway dashboard → Backend Service → Settings → Shell:
```bash
python scripts/create_admin.py
```

---

### Step 7: Deploy Frontend to Vercel (5 min)
1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub
3. Click "New Project"
4. Import your `coredent-style-main` repository
5. Add Environment Variable:
   ```bash
   VITE_API_URL=https://[project-name].up.railway.app
   ```
6. Click "Deploy"
7. Your frontend is live at: `https://[project-name].vercel.app`

---

### Step 8: Update CORS Settings (1 min)
In Railway → Backend Service → Variables, update:
```bash
CORS_ORIGINS=https://[project-name].vercel.app
FRONTEND_URL=https://[project-name].vercel.app
```

---

### Step 9: Test Everything (2 min)
1. Open: `https://[project-name].vercel.app`
2. Login with your admin credentials
3. Test:
   - [ ] Can login
   - [ ] Can create a patient
   - [ ] Can schedule an appointment
   - [ ] Can create an invoice

---

## 💰 Cost Summary

| Service | What | Cost |
|---------|------|------|
| Railway | Database + Backend | $10/month |
| Vercel | Frontend | Free |
| **Total** | | **$10/month** |

**Your price:** $499/month per practice  
**Your cost:** $10/month  
**Profit:** $489/month (98% margin!) 🚀

---

## 📋 Complete Command Sequence

```bash
# 1. Create Railway account at railway.app
# 2. Add PostgreSQL service (one click)
# 3. Connect GitHub repo for backend
# 4. Set environment variables in Railway dashboard
# 5. Deploy frontend to Vercel
# 6. Update CORS settings
# 7. Test at https://your-app.vercel.app
```

---

## 🔧 Environment Variables for Railway

### Backend Service Variables:
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
SECRET_KEY=[generate with: openssl rand -hex 32]
DEBUG=False
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend.vercel.app
FRONTEND_URL=https://your-frontend.vercel.app
RATE_LIMIT_PER_MINUTE=100
SESSION_TIMEOUT_MINUTES=15
PASSWORD_MIN_LENGTH=12
AUDIT_LOG_ENABLED=True
```

### Frontend (Vercel) Variables:
```bash
VITE_API_URL=https://your-backend.up.railway.app
```

---

## 🚀 Deploy Commands

### Backend Start Command (Railway):
```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend Build Command (Vercel):
```bash
npm run build
```

---

## ✅ Launch Checklist

- [ ] Railway account created
- [ ] PostgreSQL database added
- [ ] Backend service connected to GitHub
- [ ] Environment variables set
- [ ] Database migration run
- [ ] Admin user created
- [ ] Frontend deployed to Vercel
- [ ] CORS settings updated
- [ ] Login tested
- [ ] Core features tested

---

## 🆘 Troubleshooting

### "Module not found" errors
- Check `requirements.txt` has all dependencies
- Railway auto-installs from `requirements.txt`

### "Connection refused" errors
- Check `DATABASE_URL` is set correctly
- Railway provides this automatically from PostgreSQL service

### "CORS errors"
- Update `CORS_ORIGINS` with your Vercel domain
- Include both `http://` and `https://` if needed

### "Migration failed"
- Check database connection
- Run migration manually in Railway shell

---

## 📖 Additional Resources

- **API Documentation:** `https://your-backend.up.railway.app/docs`
- **Railway Docs:** https://docs.railway.app
- **Vercel Docs:** https://vercel.com/docs

---

## 🎯 What You're Building

| Component | Technology | Status |
|-----------|------------|--------|
| Database | PostgreSQL (Railway) | ✅ Ready |
| Backend | FastAPI (Railway) | ✅ Ready |
| Frontend | React (Vercel) | ✅ Ready |
| Security | Encryption, Rate Limiting | ✅ Built-in |
| Documentation | 40+ files | ✅ Complete |

---

**You're ready to launch! Follow the steps above in order.**