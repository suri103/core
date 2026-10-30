# Railway Quick Setup - Where to Get Everything

## Step 1: Generate SECRET_KEY

You need a random secure string. Use one of these methods:

### Method A: Online Generator (Easiest)
1. Go to: https://www.uuidgenerator.net/
2. Click "Generate" button
3. Copy the generated UUID
4. Use it as your `SECRET_KEY`

**Example:**
```
SECRET_KEY=550e8400-e29b-41d4-a716-446655440000
```

### Method B: Python (If you have Python installed)
1. Open terminal/command prompt
2. Run:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
3. Copy the output

**Example output:**
```
SECRET_KEY=Drmhze6EPcv0fN_81Bj-nA_L8w9Wyp1E7GlxstKLsKw
```

### Method C: Use a Pre-generated One
```
SECRET_KEY=your-super-secret-key-min-32-characters-long-12345
```

---

## Step 2: Get DATABASE_URL

You have two options:

### Option A: Use Railway's Built-in PostgreSQL (Recommended)

1. Go to https://railway.app
2. Open your project: `coredentist`
3. Click "Add Service" button
4. Search for "PostgreSQL"
5. Click "PostgreSQL"
6. Railway will create a database automatically
7. Click on the PostgreSQL service
8. Go to "Variables" tab
9. Copy the `DATABASE_URL` value

**It will look like:**
```
DATABASE_URL=postgresql://postgres:password123@containers-us-west-123.railway.app:5432/railway
```

### Option B: Use External Database

If you have your own PostgreSQL database:

**Format:**
```
DATABASE_URL=postgresql://username:password@host:port/database_name
```

**Example:**
```
DATABASE_URL=postgresql://admin:mypassword123@db.example.com:5432/coredent_db
```

**Where to find each part:**
- `username` = Your database user (usually `postgres` or `admin`)
- `password` = Your database password
- `host` = Your database server address (IP or domain)
- `port` = Usually `5432` for PostgreSQL
- `database_name` = Name of your database

---

## Step 3: Add Variables to Railway

### Step-by-Step Instructions:

1. **Open Railway Dashboard**
   - Go to https://railway.app
   - Sign in with GitHub

2. **Select Your Project**
   - Click on `coredentist` project
   - Click on the deployment (the one that's crashing)

3. **Go to Variables Tab**
   - Look for tabs at the top: "Deployments", "Variables", "Metrics", "Settings"
   - Click "Variables"

4. **Add DATABASE_URL**
   - Click "Add Variable" button
   - In the "Key" field, type: `DATABASE_URL`
   - In the "Value" field, paste your database URL
   - Click "Add"

5. **Add SECRET_KEY**
   - Click "Add Variable" button again
   - In the "Key" field, type: `SECRET_KEY`
   - In the "Value" field, paste your secret key
   - Click "Add"

6. **Redeploy**
   - Click the "Redeploy" button
   - Wait for the deployment to complete (2-3 minutes)
   - Check the logs to see if it starts successfully

---

## Step 4: Run Migrations

Once the app is running:

1. **Open Railway Shell**
   - In Railway dashboard, click "Shell" tab
   - You'll see a terminal

2. **Run Migration Command**
   - Type this command:
   ```bash
   alembic upgrade head
   ```
   - Press Enter
   - Wait for it to complete

3. **Check for Success**
   - You should see: `INFO  [alembic.runtime.migration] Running upgrade ...`
   - If no errors, migrations are done!

---

## Complete Example

### Your Variables Should Look Like:

```
DATABASE_URL = postgresql://postgres:mypassword@containers-us-west-123.railway.app:5432/railway
SECRET_KEY = Drmhze6EPcv0fN_81Bj-nA_L8w9Wyp1E7GlxstKLsKw
ENVIRONMENT = production
DEBUG = false
```

### After Adding:
1. Click "Redeploy"
2. Wait 2-3 minutes
3. Check logs - should say "Application startup complete"
4. Run migrations in Shell: `alembic upgrade head`
5. Done! Your app is live

---

## Troubleshooting

### "Connection refused" Error
- Database URL is wrong
- Check host/port/credentials
- Make sure database is running

### "Field required" Error
- Missing `DATABASE_URL` or `SECRET_KEY`
- Go back to Variables tab
- Make sure both are added

### Migrations Failed
- Run again: `alembic upgrade head`
- Check if database is accessible
- Look at error message for details

---

## Quick Checklist

- [ ] Generated `SECRET_KEY` (use UUID generator or Python)
- [ ] Got `DATABASE_URL` (from Railway PostgreSQL or external DB)
- [ ] Added `DATABASE_URL` to Railway Variables
- [ ] Added `SECRET_KEY` to Railway Variables
- [ ] Clicked "Redeploy"
- [ ] Waited for deployment to complete
- [ ] Ran `alembic upgrade head` in Shell
- [ ] App is running! ✅

---

## Need Help?

If something doesn't work:
1. Check the "Deploy Logs" tab in Railway
2. Look for error messages
3. Make sure variables are spelled correctly (case-sensitive)
4. Try redeploying again
