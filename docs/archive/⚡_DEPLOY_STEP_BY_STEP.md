# ⚡ How to Deploy - Step by Step

## Current Situation
- Backend is crashing (needs ENCRYPTION_KEY)
- Frontend is crashed (needs redeploy)
- You need to fix both in Railway dashboard

---

## Step 1: Open Railway Dashboard

1. Go to: https://railway.app
2. Login with your account
3. You should see your project with 2 services:
   - Backend (coredentist-production) - CRASHED ❌
   - Frontend (respectful-strength...) - CRASHED ❌

---

## Step 2: Fix Backend (Add Encryption Key)

### 2.1 Click on Backend Service
- Click the backend service card (the one that's crashing)

### 2.2 Go to Variables Tab
- On the left sidebar, click **"Variables"**
- You'll see existing variables like `DATABASE_URL`, `SECRET_KEY`, etc.

### 2.3 Add New Variable
1. Click **"New Variable"** button (top right)
2. In the popup:
   - **Variable name**: Type `ENCRYPTION_KEY`
   - **Value**: Copy and paste this:
     ```
     B1U2nUJYL_YIiPpu1sULzPT_MNXdOwxqXl-jnnDRP3U
     ```
3. Click **"Add"** button

### 2.4 Wait for Auto-Deploy
- Railway will automatically redeploy the backend
- Watch the **"Deployments"** tab
- Wait 2-3 minutes
- Look for: ✅ "Deployment successful"

### 2.5 Check Logs
- Click **"Logs"** tab
- You should see:
  ```
  ✅ Starting CoreDent API on port 8080
  ```
- If you see this, backend is WORKING! ✅

---

## Step 3: Fix Frontend (Redeploy)

### 3.1 Go Back to Project
- Click the back arrow or project name at top

### 3.2 Click Frontend Service
- Click the frontend service card

### 3.3 Check if Service Exists
**If service is completely gone:**
- Click **"New"** → **"GitHub Repo"**
- Select your repository
- Choose `coredent-style-main` as root directory
- Railway will auto-detect Dockerfile
- Click **"Deploy"**

**If service exists but crashed:**
- Click **"Deployments"** tab
- Click **"Deploy"** button (top right)
- Or click the three dots ⋮ on latest deployment
- Click **"Redeploy"**

### 3.4 Wait for Deploy
- Watch the deployment progress
- Wait 2-3 minutes
- Look for: ✅ "Deployment successful"

### 3.5 Get Frontend URL
- Click **"Settings"** tab
- Scroll to **"Domains"** section
- Copy the domain URL (looks like: `xxx.up.railway.app`)

---

## Step 4: Update CORS (Connect Frontend to Backend)

### 4.1 Go Back to Backend Service
- Click back arrow
- Click backend service

### 4.2 Update CORS Variable
1. Click **"Variables"** tab
2. Find `CORS_ORIGINS` variable
3. Click the **pencil icon** ✏️ to edit
4. Update value to include your frontend URL:
   ```
   https://[YOUR-FRONTEND-URL].up.railway.app
   ```
   Example:
   ```
   https://respectful-strength-production-ef28.up.railway.app
   ```
5. Click **"Update"**

### 4.3 Backend Auto-Redeploys
- Railway will redeploy backend with new CORS
- Wait 1-2 minutes

---

## Step 5: Test Your Application

### 5.1 Open Frontend
- Open your frontend URL in browser
- You should see the login page

### 5.2 Login
- Email: `admin@coredent.com`
- Password: `Admin123!`
- Click **"Sign In"**

### 5.3 Check if It Works
**Success looks like:**
- ✅ Login succeeds
- ✅ Redirects to dashboard
- ✅ No errors in browser console (press F12)

**If you see errors:**
- Open browser console (F12)
- Copy the error message
- Share it with me

---

## Visual Guide - Where to Click

### Railway Dashboard Layout:
```
┌─────────────────────────────────────┐
│  Project Name                       │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────┐  ┌──────────────┐│
│  │   Backend    │  │  Frontend    ││
│  │   Service    │  │   Service    ││
│  │              │  │              ││
│  │  [CRASHED]   │  │  [CRASHED]   ││
│  └──────────────┘  └──────────────┘│
│                                     │
└─────────────────────────────────────┘
```

### Inside a Service:
```
Left Sidebar:
- Deployments  ← Click here to redeploy
- Variables    ← Click here to add ENCRYPTION_KEY
- Settings     ← Click here to see domain URL
- Logs         ← Click here to check if working
- Metrics
```

---

## Quick Checklist

Use this to track your progress:

- [ ] Opened Railway dashboard
- [ ] Clicked backend service
- [ ] Added `ENCRYPTION_KEY` variable
- [ ] Waited for backend to redeploy
- [ ] Checked backend logs (should see "Starting CoreDent API")
- [ ] Clicked frontend service
- [ ] Redeployed frontend
- [ ] Copied frontend URL
- [ ] Updated backend `CORS_ORIGINS` with frontend URL
- [ ] Waited for backend to redeploy again
- [ ] Opened frontend URL in browser
- [ ] Logged in with admin@coredent.com / Admin123!
- [ ] Saw dashboard (SUCCESS!)

---

## Common Issues

### Backend still crashing?
- Check Variables tab - make sure `ENCRYPTION_KEY` is there
- Check Logs tab - what's the error message?

### Frontend not loading?
- Check Deployments tab - is it "Active"?
- Check Settings → Domains - is there a URL?

### Login not working?
- Check browser console (F12) for errors
- Make sure `CORS_ORIGINS` includes your frontend URL
- Try clearing browser cookies

### 403 Forbidden errors?
- Backend `CORS_ORIGINS` doesn't include frontend URL
- Update it and wait for redeploy

---

## What Each Variable Does

| Variable | What It Does |
|----------|--------------|
| `ENCRYPTION_KEY` | Encrypts patient data (SSN, medical records) |
| `DATABASE_URL` | Connects to PostgreSQL database |
| `SECRET_KEY` | Signs JWT tokens for authentication |
| `CORS_ORIGINS` | Allows frontend to call backend API |
| `ENVIRONMENT` | Tells app it's in production mode |

---

## After Everything Works

Once login works and you see the dashboard:

1. **Set up custom domain** (optional but recommended)
   - Read: `🚀_CUSTOM_DOMAIN_SETUP_GUIDE.md`
   - Get a .com domain
   - Use `app.yourdomain.com` for frontend
   - Use `api.yourdomain.com` for backend

2. **Set up email** (for password resets)
   - Use SendGrid or Mailgun
   - Add SMTP credentials to backend variables

3. **Set up backups** (important!)
   - Railway has automatic database backups
   - Check Settings → Database → Backups

---

## Need Help?

If something doesn't work:
1. Take a screenshot of the error
2. Copy the error message from logs
3. Share it with me

**You're almost there - just need to add that encryption key and redeploy!**
