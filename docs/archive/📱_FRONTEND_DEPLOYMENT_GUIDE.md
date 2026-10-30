# 📱 Frontend Deployment Guide - Railway

## ✅ Prerequisites Complete

- ✅ Backend deployed and healthy
- ✅ Database connected and migrated
- ✅ Nginx config fixed (no redirect loop)
- ✅ Code pushed to GitHub

## 🚀 Deploy Frontend (3 Easy Steps)

### Step 1: Create Railway Service (2 minutes)

1. **Open Railway Dashboard**
   - Go to: https://railway.app/project/practical-dream

2. **Add New Service**
   - Click "+ New" button (top right)
   - Select "GitHub Repo"
   - Choose: `suraiamkapooram10008-lgtm/coredentist`
   - Click "Add Service"

3. **Configure Root Directory**
   - Click on the new service (it will have a random name)
   - Go to "Settings" tab
   - Find "Root Directory" setting
   - Set to: `coredent-style-main`
   - Click "Update"

4. **Rename Service (Optional)**
   - In Settings, find "Service Name"
   - Change to: `coredentist-frontend`
   - Click "Update"

### Step 2: Add Environment Variables (1 minute)

1. **Click "Variables" tab**

2. **Add these variables:**

```
VITE_API_URL=https://coredentist-production.up.railway.app
NODE_ENV=production
```

**How to add:**
- Click "New Variable"
- Enter name: `VITE_API_URL`
- Enter value: `https://coredentist-production.up.railway.app`
- Click "Add"
- Repeat for `NODE_ENV`

### Step 3: Generate Domain & Deploy (2 minutes)

1. **Go to Settings tab**

2. **Scroll to "Networking" section**

3. **Click "Generate Domain"**
   - Railway will create a URL like: `coredentist-frontend.up.railway.app`
   - Copy this URL - you'll need it!

4. **Wait for Deployment**
   - Railway auto-deploys when you add variables
   - Watch "Deployments" tab for progress
   - Build takes ~5 minutes

### Step 4: Update Backend CORS (1 minute)

1. **Go back to backend service** (`coredentist`)

2. **Click "Variables" tab**

3. **Update CORS_ORIGINS:**
   - Find `CORS_ORIGINS` variable
   - Change value to: `["https://YOUR-FRONTEND-URL.up.railway.app"]`
   - Replace with your actual frontend URL from Step 3
   - Example: `["https://coredentist-frontend.up.railway.app"]`

4. **Backend will auto-redeploy** (1-2 minutes)

## ✅ Test Your Application

Once both services are deployed:

### 1. Test Frontend
Open: `https://YOUR-FRONTEND-URL.up.railway.app`

Should see:
- ✅ Login page loads
- ✅ No console errors
- ✅ UI looks correct

### 2. Test Backend Connection
Try to login or register:
- ✅ API calls work
- ✅ No CORS errors
- ✅ Can create account
- ✅ Can login

### 3. Test Full Flow
- ✅ Login successful
- ✅ Dashboard loads
- ✅ Can view patients
- ✅ Can create appointments
- ✅ All features work

## 🎯 Expected Build Output

Railway will:
1. Clone your repo
2. Navigate to `coredent-style-main/`
3. Run `npm ci` (install dependencies)
4. Run `npm run build` (build Vite app)
5. Build Docker image with nginx
6. Deploy to Railway domain
7. Service becomes available

**Build time:** ~5-7 minutes

## 🔧 Troubleshooting

### Frontend doesn't load
- Check Railway logs for build errors
- Verify `coredent-style-main` root directory is set
- Check Dockerfile exists in that directory

### CORS errors in browser console
- Verify CORS_ORIGINS includes frontend URL
- Check backend redeployed after CORS update
- Ensure URL format is correct (with https://)

### API calls fail
- Check VITE_API_URL is correct
- Verify backend is healthy: `/health` endpoint
- Check browser Network tab for actual error

### Build fails
- Check package.json has all dependencies
- Verify Node version compatibility
- Check Railway logs for specific error

## 📊 Service Architecture

After deployment, you'll have:

```
┌─────────────────────────────────────┐
│  Railway Project: practical-dream   │
├─────────────────────────────────────┤
│                                     │
│  Service 1: coredentist (Backend)   │
│  URL: coredentist-production...     │
│  - FastAPI + Python 3.12            │
│  - PostgreSQL database              │
│  - Port: Auto (Railway assigns)     │
│                                     │
│  Service 2: coredentist-frontend    │
│  URL: coredentist-frontend...       │
│  - React + Vite + TypeScript        │
│  - Nginx web server                 │
│  - Port: 80 (internal)              │
│                                     │
│  Service 3: PostgreSQL              │
│  - Managed database                 │
│  - Auto-linked to backend           │
│                                     │
└─────────────────────────────────────┘
```

## 🎉 Success Checklist

- [ ] Frontend service created
- [ ] Root directory set to `coredent-style-main`
- [ ] Environment variables added
- [ ] Domain generated
- [ ] Build completed successfully
- [ ] Backend CORS updated
- [ ] Frontend loads in browser
- [ ] Can login/register
- [ ] API calls work
- [ ] No console errors

## 🚀 Next Steps After Deployment

1. **Custom Domain (Optional)**
   - Add your own domain in Railway settings
   - Update DNS records
   - Railway provides SSL automatically

2. **Monitoring**
   - Watch Railway metrics
   - Check logs regularly
   - Set up alerts

3. **Environment Variables**
   - Add analytics keys if needed
   - Configure Sentry for error tracking
   - Add any other API keys

4. **Testing**
   - Test all features thoroughly
   - Check mobile responsiveness
   - Verify security headers

## 📝 Important URLs

**Railway Dashboard:**
https://railway.app/project/practical-dream

**Backend API:**
https://coredentist-production.up.railway.app

**Backend Health:**
https://coredentist-production.up.railway.app/health

**Backend Docs:**
https://coredentist-production.up.railway.app/docs

**Frontend:**
(Will be generated in Step 3)

---

**Current Status:** Ready to deploy frontend
**Next Action:** Follow Step 1 above to create Railway service
