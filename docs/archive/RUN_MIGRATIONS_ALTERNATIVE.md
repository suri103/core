# How to Run Migrations - Alternative Methods

If you can't see the Shell tab, use one of these methods instead:

---

## Method 1: Use Railway CLI (Recommended)

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login to Railway
```bash
railway login
```
- Opens browser to authenticate
- Click "Authorize"

### Step 3: Link Your Project
```bash
railway link
```
- Select your project: `coredentist`
- Select the backend service

### Step 4: Run Migrations
```bash
railway run alembic upgrade head
```

Done! Migrations will run.

---

## Method 2: Wait for Shell Tab to Appear

Sometimes the Shell tab takes a few minutes to appear:

1. Refresh the Railway dashboard page
2. Wait 2-3 minutes
3. Shell tab should appear
4. Run: `alembic upgrade head`

---

## Method 3: Skip Migrations for Now (Not Recommended)

If you want to test the app without migrations:

1. The app is already running
2. You can test basic endpoints
3. Run migrations later when Shell is available

**Note:** Some features won't work without migrations (database tables won't exist)

---

## Method 4: Run Migrations Locally

If you have Python installed locally:

### Step 1: Get Database Connection String
1. Go to Railway dashboard
2. Click on PostgreSQL service
3. Go to "Variables" tab
4. Copy `DATABASE_URL`

### Step 2: Run Migrations Locally
```bash
# Set the database URL
export DATABASE_URL="your-connection-string-here"

# Navigate to backend directory
cd coredent-api

# Run migrations
alembic upgrade head
```

---

## Recommended: Use Railway CLI (Method 1)

It's the easiest and most reliable:

```bash
# 1. Install
npm install -g @railway/cli

# 2. Login
railway login

# 3. Link project
railway link

# 4. Run migrations
railway run alembic upgrade head
```

Takes about 2 minutes total.

---

## Check if Migrations Worked

After running migrations, check the logs:

1. Railway dashboard → "Deploy Logs" tab
2. Look for: `INFO  [alembic.runtime.migration] Running upgrade`
3. If you see it, migrations worked!

---

## Troubleshooting

### "Command not found: railway"
- Make sure you installed: `npm install -g @railway/cli`
- Restart terminal after installing

### "Not authenticated"
- Run: `railway login`
- Follow the browser prompt

### "Project not linked"
- Run: `railway link`
- Select your project

### Migrations Still Fail
- Check database connection
- Make sure `DATABASE_URL` is set in Railway Variables
- Try again: `railway run alembic upgrade head`

---

## Next Steps After Migrations

Once migrations are done:

1. ✅ Backend is running
2. ✅ Database is set up
3. Deploy frontend (next step)
4. Connect frontend to backend
5. Test the app

---

## Quick Command Reference

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Run migrations
railway run alembic upgrade head

# View logs
railway logs

# SSH into container
railway shell
```

Use whichever method works best for you!
