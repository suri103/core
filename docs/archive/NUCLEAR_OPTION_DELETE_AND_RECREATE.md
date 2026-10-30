# NUCLEAR OPTION - Delete and Recreate Frontend Service

The current frontend service is stuck in a build loop. Let's delete it and start fresh.

## Step 1: Delete Current Frontend Service

1. Go to: https://railway.app/project/practical-dream
2. Click on **respectful-strength-production-ef28** (frontend service)
3. Click **Settings** tab (scroll down)
4. Click **Delete Service** (red button at bottom)
5. Confirm deletion

## Step 2: Create New Frontend Service

1. Go back to project: https://railway.app/project/practical-dream
2. Click **+ New** button
3. Select **GitHub Repo**
4. Select your repo: `suraiamkapooram10008-lgtm/coredentist`
5. Select **Root Directory**: `coredent-style-main`
6. Click **Deploy**

## Step 3: Configure Environment Variables (BEFORE build starts)

While it's deploying, go to the new frontend service:
1. Click **Variables** tab
2. Add these variables:
   - `VITE_API_BASE_URL` = `https://coredentist-production.up.railway.app/api/v1`
   - `VITE_ENABLE_DEMO_MODE` = `false`
   - `VITE_DEBUG` = `false`

3. Click **Save**

## Step 4: Wait for Build

The build will start automatically. Wait 5-10 minutes for it to complete.

## Step 5: Generate Domain

Once deployed:
1. Click the new frontend service
2. Go to **Settings** tab
3. Find **Domains** section
4. Click **Generate Domain** button
5. Copy the generated domain

## Step 6: Update Backend CORS

1. Click **coredentist** (backend service)
2. Click **Variables** tab
3. Update `CORS_ORIGINS` to include the new frontend domain
4. Save

Done!
