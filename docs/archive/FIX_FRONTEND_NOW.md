# 🔧 Fix Frontend - Missing Environment Variables

## Problem
Frontend crashed because environment variables are not set:
- ❌ `VITE_API_URL` - not set
- ❌ `VITE_APP_NAME` - not set

## Solution: Add Variables to Frontend Service

### Step 1: Go to Railway Dashboard
1. Open: https://railway.app
2. Go to: **practical-dream** project
3. Click: **frontend** service

### Step 2: Click Variables Tab
1. Click **Variables** tab
2. Click **New Variable** button

### Step 3: Add VITE_API_URL
**Variable Name:**
```
VITE_API_URL
```

**Variable Value:**
```
https://coredentist-production.up.railway.app
```

Click **Save**

### Step 4: Add VITE_APP_NAME
**Variable Name:**
```
VITE_APP_NAME
```

**Variable Value:**
```
CoreDent
```

Click **Save**

### Step 5: Restart Frontend Service
1. Click menu (⋮) in top right
2. Select **Restart**
3. Wait 2-3 minutes for restart

---

## Verification

After restart, check:
1. Frontend loads at: https://determined-nurturing-production-2704.up.railway.app
2. Should see login page
3. No errors in browser console (F12)

---

## Current Frontend Variables Status

| Variable | Status | Value |
|----------|--------|-------|
| `VITE_API_URL` | ❌ Missing | Should be: https://coredentist-production.up.railway.app |
| `VITE_APP_NAME` | ❌ Missing | Should be: CoreDent |

---

## Why This Happened

Frontend needs these variables to:
- `VITE_API_URL`: Know where the backend API is located
- `VITE_APP_NAME`: Display the app name in the UI

Without them, the frontend can't build or run properly.

---

## Quick Checklist

- [ ] Opened Railway dashboard
- [ ] Went to frontend service
- [ ] Clicked Variables tab
- [ ] Added VITE_API_URL = https://coredentist-production.up.railway.app
- [ ] Added VITE_APP_NAME = CoreDent
- [ ] Clicked Restart
- [ ] Waited 2-3 minutes
- [ ] Tested frontend loads
- [ ] No errors in console

---

## If Still Not Working

1. Check Railway logs for build errors
2. Verify variables were saved correctly
3. Try restarting again
4. Clear browser cache (Ctrl+Shift+Delete)
5. Try incognito window

