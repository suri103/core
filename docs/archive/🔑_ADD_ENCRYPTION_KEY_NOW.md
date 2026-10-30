# 🔑 URGENT: Add ENCRYPTION_KEY to Railway

## Problem

Backend is crashing with:
```
ValueError: SECURITY: ENCRYPTION_KEY must be set in production
```

## Solution: Add Environment Variable in Railway

### Step 1: Generate Encryption Key

Run this command in your terminal to generate a secure key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

This will output something like:
```
xK9mP2vL8nQ4rT6wY1zA3bC5dE7fG9hJ0kM2nP4qR6s
```

**Copy this key!**

### Step 2: Add to Railway Backend

1. Go to Railway dashboard: https://railway.app
2. Click on your **backend service** (coredentist-production)
3. Click **"Variables"** tab
4. Click **"New Variable"**
5. Add:
   - **Variable Name**: `ENCRYPTION_KEY`
   - **Value**: [paste the key you generated]
6. Click **"Add"**

Railway will automatically redeploy the backend.

---

## Alternative: Quick Copy-Paste

If you want to use a pre-generated key (for testing only):

```
ENCRYPTION_KEY=xK9mP2vL8nQ4rT6wY1zA3bC5dE7fG9hJ0kM2nP4qR6sT8uV0wX2yZ4aB6cD8eF0g
```

**⚠️ For production, generate your own unique key!**

---

## What This Key Does

The `ENCRYPTION_KEY` is used to:
- Encrypt sensitive patient data (SSN, medical records)
- Encrypt payment information
- Secure PHI (Protected Health Information) for HIPAA compliance

This is required for production to ensure data security.

---

## After Adding the Key

1. Railway will auto-redeploy the backend (takes 2-3 minutes)
2. Check the logs - should see "Starting CoreDent API on port 8080"
3. No more "ENCRYPTION_KEY must be set" errors

---

## Quick Command to Generate Key

**Windows PowerShell:**
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Linux/Mac:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## All Required Environment Variables

Make sure your Railway backend has these variables:

| Variable | Example Value | Required |
|----------|---------------|----------|
| `DATABASE_URL` | postgresql://... | ✅ Yes |
| `ENCRYPTION_KEY` | xK9mP2vL8nQ4r... | ✅ Yes |
| `SECRET_KEY` | auto-generated | ✅ Yes |
| `CORS_ORIGINS` | https://frontend-url | ✅ Yes |
| `ENVIRONMENT` | production | ✅ Yes |
| `FRONTEND_URL` | https://frontend-url | Optional |

---

**Do this now - backend won't start without it!**
