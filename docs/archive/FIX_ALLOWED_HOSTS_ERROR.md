# Fix ALLOWED_HOSTS Error - Do This Now

## The Problem
Your backend is crashing with this error:
```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
error parsing value for field "ALLOWED_HOSTS" from source "EnvSettingsSource"
```

This happens because you set `ALLOWED_HOSTS` as a plain string, but Pydantic expects JSON format for List types.

## The Solution (2 minutes)

### Option 1: Delete the Variable (RECOMMENDED)
1. Go to Railway dashboard: https://railway.app/project/practical-dream
2. Click on your `coredentist` service
3. Click the "Variables" tab
4. Find `ALLOWED_HOSTS` variable
5. Click the trash icon to delete it
6. Click "Redeploy" button at the top

**Why this works:** `ALLOWED_HOSTS` has a default value of `[]` in the code, so it's completely optional.

### Option 2: Fix the Format
If you want to keep it, change the value to JSON array format:
```json
["coredentist-production.up.railway.app"]
```

Or for multiple hosts:
```json
["coredentist-production.up.railway.app", "www.coredentist.com"]
```

## After the Fix

Once redeployed, test your backend:
- Health check: https://coredentist-production.up.railway.app/health
- API docs: https://coredentist-production.up.railway.app/docs

You should see the API documentation page instead of "Invalid host header".

## Why Did This Happen?

The `ALLOWED_HOSTS` field is defined as `List[str]` in Python. When you set it as a plain string in Railway, Pydantic tries to parse it as JSON first (before the custom validator runs), which fails.

The validator that handles comma-separated strings only runs AFTER Pydantic successfully parses the environment variable, so it never gets a chance to convert your string.

## Next Steps After Backend Works

1. Deploy frontend to Railway as a separate service
2. Configure frontend with `VITE_API_URL=https://coredentist-production.up.railway.app`
3. Update CORS_ORIGINS in backend to include frontend URL
