# UPDATE BACKEND CORS - DO THIS NOW IN RAILWAY

## Current Issue
Backend CORS is still pointing to old frontend URL: `determined-nurturing-production-2704.up.railway.app`
Frontend is now at: `respectful-strength-production-ef28.up.railway.app`

## Fix - Update Backend Environment Variable

1. Go to: https://railway.app/project/practical-dream

2. Click on **coredentist** service (the backend)

3. Click **Variables** tab

4. Find the variable: `CORS_ORIGINS`

5. **Replace the value with:**
```
https://respectful-strength-production-ef28.up.railway.app,https://coredentist-production.up.railway.app
```

6. Click **Save**

7. The backend will automatically restart with the new CORS settings

## What This Does
- Allows frontend at `respectful-strength-production-ef28.up.railway.app` to make API calls
- Also allows backend's own domain for testing

## After Saving
Wait 30 seconds for the backend to restart, then the frontend will be able to communicate with the backend.
