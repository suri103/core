# 🚀 Railway Setup - Do This Now

Your backend is **DEPLOYED AND WORKING** - it just needs environment variables!

## Current Status
✅ Backend builds successfully  
✅ Docker container starts  
❌ Crashes because `DATABASE_URL` and `SECRET_KEY` are missing

---

## Step 1: Add PostgreSQL Database

1. Go to your Railway project: https://railway.app/project/practical-dream
2. Click **"+ New"** button
3. Select **"Database"** → **"PostgreSQL"**
4. Railway will create a PostgreSQL database and generate a connection string

---

## Step 2: Add Environment Variables

1. Click on your **"coredentist"** service
2. Go to the **"Variables"** tab
3. Click **"+ New Variable"** and add these:

### Required Variables

```bash
# Database (copy from Railway PostgreSQL service)
DATABASE_URL=postgresql://postgres:password@host:5432/railway

# Security Key (generate a random 32+ character string)
SECRET_KEY=your-random-32-character-secret-key-here

# Frontend URL (your Railway frontend URL once deployed)
FRONTEND_URL=https://your-frontend.railway.app

# CORS Origins (your frontend URL)
CORS_ORIGINS=https://your-frontend.railway.app

# Environment
ENVIRONMENT=production
DEBUG=False
```

### How to Get DATABASE_URL
1. Click on your PostgreSQL service in Railway
2. Go to **"Variables"** tab
3. Copy the value of `DATABASE_URL`
4. Paste it into your coredentist service variables

### How to Generate SECRET_KEY
Run this command on your computer:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy the output and use it as your `SECRET_KEY`

---

## Step 3: Redeploy

1. After adding all variables, click **"Redeploy"** button
2. Wait for deployment to complete (1-2 minutes)
3. Your backend should now be running!

---

## Step 4: Run Database Migrations

Once the backend is running, you need to create the database tables.

### Option A: Railway Dashboard (Easiest)
1. Go to your coredentist service
2. Click on **"Deployments"** tab
3. Click on the latest deployment
4. Look for a **"Shell"** or **"Terminal"** button
5. If available, run:
```bash
alembic upgrade head
```

### Option B: Local Railway CLI
```bash
# In your project directory
railway link
# Select: practical-dream → production → coredentist

# Run migrations
railway run alembic upgrade head
```

### Option C: Connect Locally
```bash
# Get your DATABASE_URL from Railway
# Then run migrations locally pointing to Railway database
alembic upgrade head
```

---

## Step 5: Test Your Backend

Once migrations are complete, test your API:

```bash
# Get your Railway URL (something like: https://coredentist-production.up.railway.app)
curl https://your-backend-url.railway.app/health
```

You should see:
```json
{"status": "healthy"}
```

---

## Next: Deploy Frontend

After backend is working:

1. Create a new Railway service for frontend
2. Point it to `coredent-style-main` folder
3. Add environment variable:
   ```
   VITE_API_URL=https://your-backend-url.railway.app
   ```
4. Deploy!

---

## Troubleshooting

### "No config file 'alembic.ini' found"
This happens when running `railway run` locally - it runs on your machine, not in the container.

**Solution:** Use Railway dashboard Shell or connect to the database directly.

### "Field required" errors
Make sure you added ALL required variables:
- `DATABASE_URL`
- `SECRET_KEY`
- `FRONTEND_URL`
- `CORS_ORIGINS`

### Backend still crashing
1. Check the logs in Railway dashboard
2. Make sure `DATABASE_URL` is correct (copy from PostgreSQL service)
3. Make sure `SECRET_KEY` is at least 32 characters

---

## Quick Reference

**Railway Project:** practical-dream  
**Service:** coredentist  
**Branch:** master  
**Region:** us-east4

**Required Variables:**
- DATABASE_URL (from PostgreSQL service)
- SECRET_KEY (generate with Python command above)
- FRONTEND_URL (your frontend URL)
- CORS_ORIGINS (your frontend URL)
- ENVIRONMENT=production
- DEBUG=False
