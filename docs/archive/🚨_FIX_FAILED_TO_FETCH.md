# 🚨 FIX: "Failed to Fetch" Error

**Error**: "Failed to fetch" when trying to login  
**Cause**: Frontend can't reach backend  
**Date**: April 9, 2026

---

## Quick Fix (Choose Your Scenario)

### Scenario 1: Testing Locally (localhost)

If you're running frontend on `http://localhost:5173`:

1. **Check if backend is running locally:**
   ```bash
   cd coredent-api
   python -m uvicorn app.main:app --reload
   ```

2. **Create `.env.local` file in `coredent-style-main/`:**
   ```bash
   cd coredent-style-main
   echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env.local
   ```

3. **Restart frontend:**
   ```bash
   npm run dev
   ```

---

### Scenario 2: Frontend on Railway, Backend on Railway

If both are deployed on Railway:

1. **Get your backend URL from Railway:**
   - Go to Railway dashboard
   - Click on backend service
   - Copy the public URL (e.g., `https://coredent-api-production.up.railway.app`)

2. **Update frontend environment variable in Railway:**
   - Go to Railway dashboard
   - Click on frontend service
   - Go to "Variables" tab
   - Add/Update:
     ```
     VITE_API_BASE_URL=https://your-backend-url.railway.app/api/v1
     ```
   - Click "Deploy" to restart

3. **Update CORS in backend:**
   - Go to Railway dashboard
   - Click on backend service
   - Go to "Variables" tab
   - Add/Update:
     ```
     CORS_ORIGINS=https://your-frontend-url.railway.app,http://localhost:5173
     ```
   - Click "Deploy" to restart

---

### Scenario 3: Frontend on Vercel, Backend on Railway

If frontend is on Vercel and backend on Railway:

1. **Get your backend URL from Railway:**
   - Railway dashboard → Backend service → Copy URL

2. **Update Vercel environment variable:**
   - Go to Vercel dashboard
   - Click your project
   - Settings → Environment Variables
   - Add:
     ```
     VITE_API_BASE_URL=https://your-backend-url.railway.app/api/v1
     ```
   - Redeploy frontend

3. **Update CORS in Railway backend:**
   - Railway dashboard → Backend service → Variables
   - Add/Update:
     ```
     CORS_ORIGINS=https://your-frontend-url.vercel.app,http://localhost:5173
     ```
   - Redeploy backend

---

## Step-by-Step Diagnosis

### Step 1: Find Your Backend URL

**If backend is on Railway:**
```bash
# Go to Railway dashboard
# Click backend service
# Look for "Public Networking" section
# Copy the URL (e.g., https://coredent-api-production.up.railway.app)
```

**If backend is local:**
```bash
# Default: http://localhost:8000
```

### Step 2: Test Backend Directly

Open your browser and go to:
```
https://your-backend-url.railway.app/health
```

**Expected response:**
```json
{"status": "healthy"}
```

**If you get an error:**
- Backend is down → Check Railway logs
- 404 Not Found → Wrong URL
- Connection refused → Backend not deployed

### Step 3: Check Frontend API URL

**If running locally:**
```bash
cd coredent-style-main
cat .env.local
```

Should show:
```
VITE_API_BASE_URL=https://your-backend-url.railway.app/api/v1
```

**If deployed on Vercel/Railway:**
- Check environment variables in dashboard
- Must have `VITE_API_BASE_URL` set

### Step 4: Test CORS

Open browser console and run:
```javascript
fetch('https://your-backend-url.railway.app/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'test@test.com', password: 'test' })
})
.then(r => r.json())
.then(console.log)
.catch(console.error)
```

**If you see CORS error:**
- Backend CORS not configured
- Wrong origin in CORS_ORIGINS
- See "Fix CORS" section below

---

## Fix CORS (Backend)

### Option 1: Railway Dashboard

1. Go to Railway dashboard
2. Click backend service
3. Variables tab
4. Add/Update:
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app,https://your-frontend.railway.app,http://localhost:5173
   ```
5. Click "Deploy"

### Option 2: Update Code

Edit `coredent-api/.env` or `.env.production`:
```bash
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
```

Then push to GitHub:
```bash
git add coredent-api/.env.production
git commit -m "Update CORS origins"
git push origin main
```

Railway will auto-deploy.

---

## Common Mistakes

### ❌ Wrong: Trailing slash in API URL
```
VITE_API_BASE_URL=https://backend.railway.app/api/v1/
                                                      ^ Remove this!
```

### ✅ Correct: No trailing slash
```
VITE_API_BASE_URL=https://backend.railway.app/api/v1
```

### ❌ Wrong: Missing /api/v1
```
VITE_API_BASE_URL=https://backend.railway.app
```

### ✅ Correct: Include /api/v1
```
VITE_API_BASE_URL=https://backend.railway.app/api/v1
```

### ❌ Wrong: HTTP instead of HTTPS
```
VITE_API_BASE_URL=http://backend.railway.app/api/v1
```

### ✅ Correct: Use HTTPS for Railway
```
VITE_API_BASE_URL=https://backend.railway.app/api/v1
```

---

## Quick Test Commands

### Test backend health:
```bash
curl https://your-backend.railway.app/health
```

### Test login endpoint:
```bash
curl -X POST https://your-backend.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@coredent.com","password":"Admin123!@#"}'
```

### Check frontend environment:
```bash
cd coredent-style-main
cat .env.local
```

---

## Still Not Working?

### Get Your URLs

1. **Backend URL:**
   - Railway dashboard → Backend service → Settings → Public Networking
   - Copy the domain (e.g., `coredent-api-production.up.railway.app`)
   - Full URL: `https://coredent-api-production.up.railway.app`

2. **Frontend URL:**
   - Vercel: Check project settings
   - Railway: Check service settings
   - Local: `http://localhost:5173`

### Update Both Sides

**Frontend needs to know backend:**
```bash
# In frontend environment variables
VITE_API_BASE_URL=https://[BACKEND-URL]/api/v1
```

**Backend needs to allow frontend:**
```bash
# In backend environment variables
CORS_ORIGINS=https://[FRONTEND-URL],http://localhost:5173
```

---

## Example Configuration

### Local Development

**Frontend (.env.local):**
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_DEV_BYPASS_AUTH=false
```

**Backend (.env):**
```bash
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
DATABASE_URL=postgresql://localhost/coredent
SECRET_KEY=your-secret-key-here
```

### Production (Railway + Vercel)

**Frontend (Vercel env vars):**
```bash
VITE_API_BASE_URL=https://coredent-api-production.up.railway.app/api/v1
```

**Backend (Railway env vars):**
```bash
CORS_ORIGINS=https://coredent.vercel.app,http://localhost:5173
DATABASE_URL=[auto-set by Railway]
SECRET_KEY=[your-secret-key]
```

---

## Checklist

Before trying to login again:

- [ ] Backend is running (test /health endpoint)
- [ ] Frontend has correct VITE_API_BASE_URL
- [ ] Backend has frontend URL in CORS_ORIGINS
- [ ] No trailing slashes in URLs
- [ ] Using HTTPS for Railway URLs
- [ ] Environment variables are saved
- [ ] Services are restarted/redeployed
- [ ] Browser cache is cleared

---

## Next Steps

Once "Failed to fetch" is fixed, you might see:
- ✅ "Invalid credentials" → Good! Backend is reachable, just wrong password
- ✅ "Account locked" → Good! Backend is working, just locked
- ❌ "CORS error" → Need to fix CORS (see above)
- ❌ "404 Not Found" → Wrong API URL

---

**Quick Fix Summary:**

1. Get backend URL from Railway
2. Set `VITE_API_BASE_URL` in frontend
3. Set `CORS_ORIGINS` in backend
4. Restart both services
5. Try login again

