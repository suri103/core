# 🖱️ Railway Dashboard - Where to Click

Visual guide for completing setup in the Railway web dashboard.

---

## 🌐 Step 1: Open Railway

Go to: **https://railway.app/project/practical-dream**

```
┌─────────────────────────────────────────────────────────┐
│  Railway Dashboard                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  practical-dream                          [+ New] ←─────┐
│                                                         │
│  ┌──────────────┐                                      │
│  │ coredentist  │  ← Your backend service              │
│  │ (Running)    │                                      │
│  └──────────────┘                                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🗄️ Step 2: Add PostgreSQL

Click **[+ New]** button → **Database** → **PostgreSQL**

```
┌─────────────────────────────────────────────────────────┐
│  Add a Service                                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Empty     │  │  Database   │  │   Template  │   │
│  │   Service   │  │      ✓      │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│  Select Database Type:                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ PostgreSQL  │  │    MySQL    │  │    Redis    │   │
│  │      ✓      │  │             │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│                              [Add PostgreSQL] ←─────────┐
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Wait for PostgreSQL to deploy (30-60 seconds).

---

## 📋 Step 3: Copy DATABASE_URL

Click **PostgreSQL** service → **Variables** tab

```
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL                                             │
├─────────────────────────────────────────────────────────┤
│  [Deployments] [Variables] [Settings] [Metrics]        │
│                    ↑                                    │
│                Click here                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Environment Variables                                  │
│                                                         │
│  DATABASE_URL                                    [📋]   │
│  postgresql://postgres:xxx@xxx.railway.app:5432/railway│
│                                                  ↑      │
│                                            Click to copy│
│                                                         │
│  PGDATABASE                                      [📋]   │
│  railway                                                │
│                                                         │
│  PGHOST                                          [📋]   │
│  xxx.railway.app                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Click the **[📋]** icon next to `DATABASE_URL` to copy it.

---

## ⚙️ Step 4: Add Variables to Backend

Click **coredentist** service → **Variables** tab → **[+ New Variable]**

```
┌─────────────────────────────────────────────────────────┐
│  coredentist                                            │
├─────────────────────────────────────────────────────────┤
│  [Deployments] [Variables] [Settings] [Metrics]        │
│                    ↑                                    │
│                Click here                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Environment Variables              [+ New Variable] ←──┐
│                                                         │
│  (Currently empty or showing error)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Add Each Variable:

```
┌─────────────────────────────────────────────────────────┐
│  Add Variable                                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Variable Name:                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ DATABASE_URL                                      │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Variable Value:                                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │ postgresql://postgres:xxx@xxx.railway.app:5432... │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│                                    [Cancel]  [Add] ←────┐
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Repeat for all 6 variables:
1. `DATABASE_URL` = [paste from PostgreSQL]
2. `SECRET_KEY` = [from generate_secret_key.py]
3. `ENVIRONMENT` = `production`
4. `DEBUG` = `False`
5. `FRONTEND_URL` = `https://coredentist.railway.app`
6. `CORS_ORIGINS` = `https://coredentist.railway.app`

---

## 🔄 Step 5: Redeploy

After adding all variables, look for the **Redeploy** button:

```
┌─────────────────────────────────────────────────────────┐
│  coredentist                                            │
├─────────────────────────────────────────────────────────┤
│  [Deployments] [Variables] [Settings] [Metrics]        │
│       ↑                                                 │
│   Click here                                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Latest Deployment                        [Redeploy] ←──┐
│                                                         │
│  Status: Failed (Missing variables)                     │
│  Time: 2 minutes ago                                    │
│                                                         │
│  [View Logs]                                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Click **[Redeploy]** and wait for deployment to complete.

---

## 📊 Step 6: Check Deployment Logs

```
┌─────────────────────────────────────────────────────────┐
│  Deployment Logs                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Building...                                            │
│  ✓ Build successful                                     │
│  Deploying...                                           │
│  ✓ Container started                                    │
│  INFO: Application startup complete                     │
│  INFO: Uvicorn running on http://0.0.0.0:8000          │
│                                                         │
│  Status: ✓ Deployment successful                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Look for "Application startup complete" - that means it's working!

---

## 🖥️ Step 7: Find Shell (If Available)

```
┌─────────────────────────────────────────────────────────┐
│  coredentist                                            │
├─────────────────────────────────────────────────────────┤
│  [Deployments] [Variables] [Settings] [Metrics]        │
│       ↑                                                 │
│   Click here                                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Latest Deployment                                      │
│                                                         │
│  [View Logs]  [Shell] ←─────────────────────────────────┐
│                  ↑                                      │
│            Click here if available                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

If you see **[Shell]** button:
1. Click it
2. Type: `alembic upgrade head`
3. Press Enter

If you DON'T see Shell button:
- Use Railway CLI (see below)

---

## 🔗 Step 8: Get Your Backend URL

Click **coredentist** → **Settings** tab

```
┌─────────────────────────────────────────────────────────┐
│  coredentist - Settings                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Service Name: coredentist                              │
│                                                         │
│  Domains:                                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │ coredentist-production.up.railway.app       [📋] │ │
│  └───────────────────────────────────────────────────┘ │
│                                                  ↑      │
│                                         Your backend URL│
│                                                         │
│  [+ Generate Domain]                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Copy this URL - you'll need it for testing and frontend setup.

---

## ✅ Step 9: Test Backend

Open a new browser tab and go to:
```
https://your-backend-url.railway.app/health
```

You should see:
```json
{"status": "healthy"}
```

---

## 🔄 If You Need to Reconnect CLI

Open PowerShell in your project folder:

```powershell
# Navigate to project
cd D:\coredentist

# Login to Railway (if needed)
railway login

# Link to your project
railway link
```

You'll see:
```
> Select a workspace: suraiamkapooram10008-lgtm's Projects
> Select a project: practical-dream
> Select an environment: production
> Select a service: coredentist

Project practical-dream linked successfully! 🎉
```

Then run migrations:
```powershell
railway run alembic upgrade head
```

---

## 📋 Quick Reference

| Task | Location | Action |
|------|----------|--------|
| Add PostgreSQL | Dashboard → + New | Database → PostgreSQL |
| Copy DATABASE_URL | PostgreSQL → Variables | Click 📋 icon |
| Add Variables | coredentist → Variables | + New Variable |
| Redeploy | coredentist → Deployments | Click Redeploy |
| View Logs | coredentist → Deployments | View Logs |
| Run Shell | coredentist → Deployments | Shell button |
| Get URL | coredentist → Settings | Copy from Domains |

---

## 🎯 Success Checklist

- [ ] PostgreSQL service created
- [ ] DATABASE_URL copied
- [ ] All 6 variables added to coredentist
- [ ] Backend redeployed
- [ ] Logs show "Application startup complete"
- [ ] Migrations run successfully
- [ ] /health endpoint returns {"status": "healthy"}
- [ ] ✅ Backend is LIVE!

---

**Everything can be done in the browser - no CLI required! 🌐**
