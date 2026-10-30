# Update Backend CORS for Frontend

## Frontend URL
```
https://heartfelt-benevolence-production-ba39.up.railway.app
```

## Steps to Update Backend in Railway

### Step 1: Go to Backend Service
1. Open Railway: https://railway.app/project/practical-dream
2. Click on **coredentist** service (the backend)

### Step 2: Update CORS_ORIGINS Variable
1. Click on the **Variables** tab
2. Find the `CORS_ORIGINS` variable
3. Update it to:
   ```
   https://heartfelt-benevolence-production-ba39.up.railway.app
   ```
4. Click **Save**

### Step 3: Backend Will Auto-Restart
- Railway will automatically restart the backend service
- Wait 30-60 seconds for it to restart
- Check the health endpoint to confirm it's running:
  ```
  https://coredentist-production.up.railway.app/health
  ```

## What This Does
- Allows the frontend to make API requests to the backend
- Prevents CORS (Cross-Origin Resource Sharing) errors
- Enables secure communication between frontend and backend

## Testing
1. Open the frontend: https://heartfelt-benevolence-production-ba39.up.railway.app
2. Try to login
3. Check browser console (F12) for any CORS errors
4. If you see CORS errors, verify the URL matches exactly

## If You Get CORS Errors
- Make sure the frontend URL in `CORS_ORIGINS` matches exactly (including https://)
- Check that the backend has restarted (look at the service logs)
- Try clearing browser cache and cookies
- Try in an incognito/private window

## Current Configuration
- Backend: https://coredentist-production.up.railway.app
- Frontend: https://heartfelt-benevolence-production-ba39.up.railway.app
- Database: PostgreSQL (auto-linked)
