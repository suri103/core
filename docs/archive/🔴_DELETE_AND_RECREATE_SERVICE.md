# 🔴 Delete and Recreate Frontend Service

Railway is caching the old broken railway.json file. We need to delete the service and create a new one.

## Step 1: Delete the Failing Service

1. Go to Railway: https://railway.app/project/practical-dream
2. Click on the **frontend service** (the one that's failing)
3. Click **"Settings"** tab
4. Scroll to the **bottom**
5. Click **"Delete Service"**
6. Confirm deletion

## Step 2: Create New Service (The Right Way)

1. Click **"+ New"** button (top right)
2. Select **"Empty Service"**
3. Click **"Create"**

## Step 3: Configure the Service

1. Click on the new empty service
2. Go to **"Settings"** tab
3. Under **"Source"** section, click **"Connect Repo"**
4. Select your repo: `suraiamkapooram10008-lgtm/coredentist`
5. Click **"Connect"**

## Step 4: Set Root Directory

**IMPORTANT - Do this BEFORE deploying:**

1. Still in Settings
2. Find **"Root Directory"** field
3. Type: `coredent-style-main`
4. Click **"Update"** or **"Save"**

## Step 5: Add Environment Variables

1. Click **"Variables"** tab
2. Click **"New Variable"**
3. Add:
   - Name: `VITE_API_URL`
   - Value: `https://coredentist-production.up.railway.app`
4. Click **"Add"**
5. Click **"New Variable"** again
6. Add:
   - Name: `NODE_ENV`
   - Value: `production`
7. Click **"Add"**

## Step 6: Generate Domain

1. Go to **"Settings"** tab
2. Scroll to **"Networking"** section
3. Click **"Generate Domain"**
4. Copy the URL (e.g., `coredentist-frontend.up.railway.app`)

## Step 7: Railway Will Auto-Deploy

Once you set the root directory and add variables, Railway will automatically start building.

Watch the "Deployments" tab for progress.

## Step 8: Update Backend CORS

After frontend is deployed:

1. Go to backend service (coredentist)
2. Variables tab
3. Update CORS_ORIGINS: `["https://YOUR-FRONTEND-URL"]`
4. Replace with actual frontend URL from Step 6

## Expected Timeline

- **Step 1-2:** 2 minutes (delete and create)
- **Step 3-5:** 3 minutes (configure)
- **Step 6-7:** 5-7 minutes (build and deploy)
- **Step 8:** 1 minute (update CORS)

**Total:** ~15 minutes

## Why This Works

- Fresh service = no cached files
- Root directory set BEFORE deployment = correct build
- No broken railway.json files = no parse errors

---

**Current:** Ready to delete and recreate
**Next:** Follow steps above
