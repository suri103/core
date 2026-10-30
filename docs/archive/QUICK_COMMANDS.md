# ⚡ Quick Commands Reference

## Generate SECRET_KEY
```bash
python generate_secret_key.py
```

OR

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Link Railway Project
```bash
cd D:\coredentist
railway link
```
Select: `practical-dream` → `production` → `coredentist`

---

## Run Migrations (After Variables Are Set)

### Option 1: Railway CLI
```bash
railway run alembic upgrade head
```

### Option 2: Railway Shell
```bash
railway shell
cd /app
alembic upgrade head
exit
```

### Option 3: Direct Database Connection
```bash
# Get DATABASE_URL from Railway
# Set it locally
set DATABASE_URL=postgresql://...
alembic upgrade head
```

---

## Test Backend Health
```bash
curl https://coredentist-production.up.railway.app/health
```

---

## View Logs
```bash
railway logs
```

---

## Check Service Status
```bash
railway status
```

---

## Environment Variables to Add

Copy-paste these into Railway Variables tab:

```bash
DATABASE_URL=[copy from PostgreSQL service]
SECRET_KEY=[generate with command above]
ENVIRONMENT=production
DEBUG=False
FRONTEND_URL=https://coredentist.railway.app
CORS_ORIGINS=https://coredentist.railway.app
```

---

## Railway Dashboard URLs

- **Project**: https://railway.app/project/practical-dream
- **Add Database**: Click "+ New" → Database → PostgreSQL
- **Add Variables**: coredentist service → Variables tab
- **View Logs**: coredentist service → Deployments → View Logs
- **Redeploy**: coredentist service → Deployments → Redeploy

---

## Verification Checklist

After setup, verify:

```bash
# 1. Backend is running
curl https://your-backend-url.railway.app/health

# 2. Database tables exist
railway shell
psql $DATABASE_URL -c "\dt"

# 3. Can create user (test endpoint)
curl -X POST https://your-backend-url.railway.app/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!@#","full_name":"Test User"}'
```

---

## Common Issues

### "No config file 'alembic.ini' found"
- You're running locally, not in container
- Use `railway shell` to run inside container

### "Field required" errors
- Environment variables not set
- Add them in Railway Dashboard → Variables
- Click "Redeploy" after adding

### "Connection refused"
- Backend not running yet
- Check logs: `railway logs`
- Make sure variables are set correctly

---

## Next Steps After Backend Works

1. Create new Railway service for frontend
2. Set `VITE_API_URL` to backend URL
3. Deploy frontend
4. Test full application
5. 🎉 You're live!
