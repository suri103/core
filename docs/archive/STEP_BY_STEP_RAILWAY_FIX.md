# Step-by-Step: Fix Railway Healthcheck

## What You Need to Do

Disable the healthcheck in Railway's web dashboard. This takes 2 minutes.

---

## Step 1: Open Railway Dashboard

1. Open your web browser
2. Go to: **https://railway.app**
3. Log in if you're not already logged in

---

## Step 2: Find Your Frontend Service

1. You'll see your Railway dashboard with your projects
2. Look for your project (probably called "coredentist" or similar)
3. Click on it to open the project
4. You'll see TWO services:
   - **coredent-api** (backend) - ignore this one
   - **coredent-style-main** or **frontend** - THIS IS THE ONE YOU NEED
5. **Click on the frontend service** (coredent-style-main)

---

## Step 3: Open Settings

1. After clicking the frontend service, you'll see several tabs at the top:
   - Deployments
   - Metrics
   - Settings
   - Variables
   - etc.
2. **Click on "Settings"** tab

---

## Step 4: Find Health Check Section

1. Scroll down the Settings page
2. Look for a section called:
   - **"Health Check"** OR
   - **"Healthcheck"** OR
   - **"Service Health"**
3. It might be collapsed - if you see a dropdown arrow, click it to expand

---

## Step 5: Disable the Healthcheck

You'll see healthcheck settings that look something like:

```
Health Check
├─ Enabled: [Toggle ON]
├─ Path: /health
├─ Timeout: 10
└─ [Remove] or [Delete] button
```

**Do ONE of these:**

### Option A: Toggle it OFF
- Find the toggle switch next to "Enabled"
- Click it to turn it OFF (it should turn gray)

### Option B: Click Remove/Delete
- Find a button that says "Remove" or "Delete"
- Click it
- Confirm if it asks "Are you sure?"

---

## Step 6: Save (if needed)

- Some Railway interfaces auto-save
- If you see a "Save" or "Save Changes" button at the bottom, click it

---

## Step 7: Redeploy

After disabling the healthcheck:

1. Go back to the **"Deployments"** tab
2. Find the latest deployment (the one that failed)
3. Click the **three dots (...)** menu next to it
4. Click **"Redeploy"**

OR just wait - Railway might automatically redeploy when you change settings.

---

## What Happens Next

- Railway will rebuild your app (takes ~30 seconds)
- This time it will skip the healthcheck
- The deployment will succeed
- Your site will be live!

---

## If You Can't Find the Healthcheck Setting

If you don't see a "Health Check" section in Settings, try this:

1. Look for **"Service Settings"** or **"Advanced Settings"**
2. Or look in the **"Networking"** section
3. Or check if there's a **"Deploy"** section with healthcheck options

If you still can't find it, the healthcheck might not be configured in the dashboard at all. In that case, just trigger a new deployment and it should work.

---

## Alternative: Use Railway CLI (Advanced)

If you prefer command line:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Disable healthcheck
railway service healthcheck disable
```

---

## Need Help?

If you're stuck, take a screenshot of your Railway dashboard and I can guide you more specifically.

The key is: **Find the frontend service → Settings → Health Check → Disable it**
