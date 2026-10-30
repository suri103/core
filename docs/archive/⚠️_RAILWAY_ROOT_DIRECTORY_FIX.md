# ⚠️ CRITICAL: Set Root Directory in Railway

## The Problem

Railway is building from the repository root (`/`) but your Dockerfile is in `coredent-api/` directory. This causes the error:

```
ERROR: "/requirements.txt": not found
```

Because Railway is looking for `requirements.txt` at the root, but it's actually at `coredent-api/requirements.txt`.

## The Solution: Configure Root Directory in Railway

### Step-by-Step Instructions

#### 1. Open Railway Dashboard
Go to: https://railway.app/dashboard

#### 2. Select Your Project
Click on your CoreDent project

#### 3. Select Backend Service
- You should see multiple services (PostgreSQL, coredent-api, maybe coredent-style-main)
- Click on the **coredent-api** service (the Python backend)

#### 4. Go to Settings
- Click the **Settings** tab at the top
- Scroll down to find the build/deployment settings

#### 5. Set Root Directory

Look for one of these settings (Railway UI varies):

**Option A: "Root Directory" field**
- Find the field labeled "Root Directory" or "Service Root"
- Enter: `coredent-api`
- Click Save

**Option B: "Build" section**
- Find "Build" or "Build Settings" section
- Look for "Root Directory", "Working Directory", or "Source Directory"
- Enter: `coredent-api`
- Click Save

**Option C: Service Settings**
- In Settings, find "Service Settings" section
- Look for "Root Directory" or "Watch Paths"
- Enter: `coredent-api`
- Click Save

#### 6. Trigger Redeploy
After saving:
- Go to **Deployments** tab
- Click **Redeploy** or **Deploy** button
- Or push a new commit to trigger auto-deploy

#### 7. Verify Build Logs
Watch the build logs. You should now see:
```
✅ COPY requirements.txt .
✅ RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
✅ Build successful
```

## Alternative: If Root Directory Setting Doesn't Exist

If Railway doesn't show a "Root Directory" setting, you have two options:

### Option 1: Create New Service from Subdirectory

1. Delete the current coredent-api service
2. Create a new service
3. During creation, select "Deploy from GitHub repo"
4. When prompted, select the `coredent-api` folder specifically
5. Railway will detect the Dockerfile automatically

### Option 2: Use Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Set root directory via CLI
railway service --root coredent-api

# Or deploy directly from subdirectory
cd coredent-api
railway up
```

## How to Verify It's Fixed

After setting the root directory and redeploying:

1. **Check Build Logs** - Should show:
   ```
   ✅ Using Detected Dockerfile
   ✅ COPY requirements.txt .
   ✅ RUN pip install ...
   ✅ Build complete
   ```

2. **Check Deployment Status** - Should show "Active" or "Running"

3. **Test Health Endpoint**:
   ```bash
   curl https://your-backend.railway.app/health
   # Should return: {"status": "healthy"}
   ```

## Common Railway UI Locations for Root Directory

Railway's UI has changed over time. Look for the setting in these places:

1. **Settings Tab** → "Service Settings" section → "Root Directory"
2. **Settings Tab** → "Build" section → "Root Directory"
3. **Settings Tab** → "Source" section → "Root Directory"
4. **Deployments Tab** → Click on a deployment → "Configuration" → "Root Directory"

## What This Setting Does

Setting `Root Directory: coredent-api` tells Railway:
- Build context starts at `coredent-api/` instead of repository root
- Dockerfile path is relative to `coredent-api/`
- All COPY commands in Dockerfile are relative to `coredent-api/`

So when Dockerfile says `COPY requirements.txt .`, Railway looks for:
- ✅ `coredent-api/requirements.txt` (correct)
- ❌ NOT `/requirements.txt` (wrong)

## Still Having Issues?

If you can't find the Root Directory setting:

1. **Take a screenshot** of your Railway service settings page
2. **Check Railway docs**: https://docs.railway.app/deploy/deployments#root-directory
3. **Contact Railway support** - they can help configure it
4. **Use Railway CLI** (see Option 2 above)

---

**Status**: ⏳ Waiting for Railway dashboard configuration  
**Time**: 2 minutes  
**Priority**: 🔴 CRITICAL - Blocking deployment

**After this fix**: Backend will deploy successfully and migrations will run automatically!
