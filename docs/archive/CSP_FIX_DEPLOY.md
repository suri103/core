# 🔒 CSP Fix - Deploy Instructions

## What Was Fixed

The Content Security Policy (CSP) in `index.html` was blocking API requests to the Railway backend. 

**Changed:**
```html
connect-src 'self' https://api.coredent.com
```

**To:**
```html
connect-src 'self' https://api.coredent.com https://coredentist-production.up.railway.app
```

## Deploy the Fix

### Option 1: Push to Git (If using Railway GitHub integration)

```bash
cd coredent-style-main
git add index.html .build-timestamp
git commit -m "Fix CSP to allow Railway backend API"
git push
```

Railway will automatically detect the change and rebuild.

### Option 2: Manual Redeploy in Railway

1. Go to Railway dashboard
2. Open your frontend service
3. Go to **Deployments** tab
4. Click the three dots (⋮) on the latest deployment
5. Select **Redeploy**

## After Deployment

Once the build completes (watch for "Deployment successful"):

1. Open: https://respectful-strength-production-ef28.up.railway.app
2. **Hard refresh** (Ctrl+Shift+R or Cmd+Shift+R) to clear browser cache
3. Login with:
   - Email: `admin@coredent.com`
   - Password: `Admin123!`

## What to Expect

✅ No more CSP errors in console  
✅ API requests will go through to backend  
✅ Login will work successfully  
✅ You'll see the dashboard after login

## If It Still Doesn't Work

Check browser console (F12) for any remaining errors and let me know what you see.

---

**Files Changed:**
- `coredent-style-main/index.html` - Updated CSP connect-src directive
- `coredent-style-main/.build-timestamp` - Triggered fresh build
