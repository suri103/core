# 🚨 URGENT: Redeploy Both Services

## Current Situation

**Frontend**: CRASHED - "Service offline - Deployment was removed because it's been crashed for too long"
**Backend**: Running but needs redeploy with updated cookie settings
**Issue**: Cross-origin authentication not working

## ✅ Solution: Redeploy Both Services

---

## Step 1: Redeploy Frontend (2 minutes)

### Option A: Redeploy from Railway Dashboard (EASIEST)

1. Go to Railway dashboard: https://railway.app
2. Find your frontend service: `respectful-strength-production-ef28`
3. Click on the service
4. Click **"Deploy"** button (top right)
5. Wait 2-3 minutes for deployment to complete
6. Check the new domain URL (it might change)

### Option B: If Service Was Deleted

If the service is completely gone:

1. Click **"New"** → **"GitHub Repo"**
2. Select your repository
3. Choose `coredent-style-main` folder
4. Railway will auto-detect Dockerfile
5. Add environment variable:
   ```
   VITE_API_BASE_URL=https://coredentist-production.up.railway.app/api/v1
   ```
6. Click **"Deploy"**
7. Wait for deployment
8. Copy the new domain URL

---

## Step 2: Redeploy Backend (2 minutes)

The backend code has been updated with `SameSite=none` for cross-origin cookies.

### In Railway Dashboard:

1. Go to your backend service: `coredentist-production`
2. Click **"Deployments"** tab
3. Click **"Deploy"** or **"Redeploy"** button
4. Wait 2-3 minutes

---

## Step 3: Update CORS if Frontend Domain Changed (1 minute)

If your frontend got a new domain URL:

1. In Railway dashboard → Backend service
2. Go to **"Variables"** tab
3. Update `CORS_ORIGINS` to include the new frontend URL:
   ```
   CORS_ORIGINS=https://[NEW-FRONTEND-URL].up.railway.app
   ```
4. Click **"Save"**
5. Backend will auto-redeploy

---

## Step 4: Test Login (2 minutes)

1. Open your frontend URL
2. Login with:
   - Email: `admin@coredent.com`
   - Password: `Admin123!`
3. Check browser console (F12) for errors

### Expected Result:

✅ Login succeeds
✅ Dashboard loads
✅ No 403 errors
✅ Cookies are sent with requests

---

## 🔍 What Was Fixed

The backend now uses `SameSite=none` instead of `SameSite=strict`:

```python
# OLD (blocked by browsers)
response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    secure=True,
    samesite="strict",  # ❌ Blocked cross-origin
)

# NEW (allows cross-origin)
response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    secure=True,
    samesite="none",  # ✅ Works cross-origin
)
```

This allows cookies to work when frontend and backend are on different domains.

---

## 🚨 If It Still Doesn't Work

### Check Browser Console (F12)

**If you see cookie warnings:**
- Make sure both services use HTTPS (Railway provides this automatically)
- Clear browser cookies and cache
- Try incognito/private browsing mode

**If you see CORS errors:**
- Verify `CORS_ORIGINS` includes your frontend URL
- Check that backend redeployed successfully

**If login returns 401:**
- Verify admin password is correct: `Admin123!`
- Check backend logs in Railway dashboard

---

## 🎯 Next Step After This Works

Once authentication works, you should set up a custom domain to avoid these cross-origin issues permanently:

**Read**: `🚀_CUSTOM_DOMAIN_SETUP_GUIDE.md`

With a custom domain:
- Frontend: `app.yourdomain.com`
- Backend: `api.yourdomain.com`
- Cookies work perfectly (same root domain)
- Professional appearance for SaaS

---

## 📊 Quick Status Check

After redeploying, verify:

| Check | Expected |
|-------|----------|
| Frontend loads | ✅ Login page appears |
| Backend responds | ✅ API returns data |
| Login works | ✅ Redirects to dashboard |
| No 403 errors | ✅ `/auth/me` returns user data |
| Cookies sent | ✅ Check Network tab in DevTools |

---

## 💡 Pro Tip

**Railway Auto-Deploys**: If you push to GitHub, Railway auto-deploys. You can disable this in Settings → "Deployments" if you want manual control.

---

**Start with Step 1 now - redeploy the frontend service!**
