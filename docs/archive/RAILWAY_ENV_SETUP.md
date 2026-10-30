# Railway Environment Variables Setup

## What Changed

The application no longer runs migrations on startup. Instead, it starts the FastAPI server immediately. This prevents crashes due to missing environment variables during the migration phase.

## Required Environment Variables

You must set these in the Railway dashboard before the app will work:

### 1. Database Configuration
```
DATABASE_URL=postgresql://user:password@host:port/database_name
```

**Example:**
```
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/coredent_db
```

### 2. Security Keys
```
SECRET_KEY=your-super-secret-key-here-min-32-chars
```

**Generate a secure key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Optional but Recommended
```
ENVIRONMENT=production
DEBUG=false
```

## How to Set Environment Variables in Railway

### Step 1: Go to Railway Dashboard
1. Open https://railway.app
2. Select your project: `coredentist`
3. Click on the deployment

### Step 2: Navigate to Variables
1. Click the "Variables" tab
2. Click "Add Variable"

### Step 3: Add Each Variable
For each variable above:
1. Enter the key (e.g., `DATABASE_URL`)
2. Enter the value
3. Click "Add"

### Step 4: Redeploy
After adding all variables:
1. Click "Redeploy" or trigger a new deployment
2. The app should now start successfully

## Database Setup

If you don't have a PostgreSQL database yet:

### Option 1: Use Railway's PostgreSQL Service
1. In your Railway project, click "Add Service"
2. Select "PostgreSQL"
3. Railway will automatically set `DATABASE_URL` for you
4. Just add `SECRET_KEY` manually

### Option 2: Use External Database
1. Get your database connection string
2. Set `DATABASE_URL` to that connection string

## Running Migrations

After the app is running, run migrations:

### Option 1: Via Railway CLI
```bash
railway run alembic upgrade head
```

### Option 2: Via SSH/Shell
1. In Railway dashboard, click "Shell"
2. Run: `alembic upgrade head`

### Option 3: Locally (if you have access to the database)
```bash
export DATABASE_URL="your-connection-string"
alembic upgrade head
```

## Troubleshooting

### "Field required" Error
- Missing `DATABASE_URL` or `SECRET_KEY`
- Check the Variables tab in Railway dashboard
- Make sure values are set correctly

### Connection Refused
- Database is not accessible from Railway
- Check database host/port/credentials
- Ensure database is running

### Migrations Failed
- Run migrations separately after app starts
- Check migration files in `coredent-api/alembic/versions/`

## Next Steps

1. ✅ Set `DATABASE_URL` in Railway Variables
2. ✅ Set `SECRET_KEY` in Railway Variables
3. ✅ Redeploy the application
4. ✅ Run migrations: `railway run alembic upgrade head`
5. ✅ Test the API: `curl https://your-railway-url/health`

Your app should now be running!
