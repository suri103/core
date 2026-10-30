# Run Database Migrations on Railway

## Quick Steps to Update Your Database

### Option 1: Run Migrations via Railway Dashboard (Recommended)

1. **Go to Railway Dashboard**
   - Open your Railway project at https://railway.app
   - Select your CoreDent project

2. **Open the Deployments Tab**
   - Click on your backend service (coredent-api)
   - Go to the "Deployments" tab

3. **Add a Start Command**
   - In your Railway dashboard, go to Settings → Build & Deploy
   - Add this to the "Start Command":
     ```
     alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - This will run migrations automatically when the app starts

4. **Redeploy**
   - Push a new commit or manually trigger a redeploy
   - Railway will run the migrations before starting the app

### Option 2: Run Migrations Manually via Railway CLI

1. **Install Railway CLI** (if not already installed)
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Connect to Your Project**
   ```bash
   railway link
   ```

4. **Run Migrations**
   ```bash
   cd coredent-api
   railway run python -m alembic upgrade head
   ```

### Option 3: Use the Provided Migration Script

1. **Navigate to the API directory**
   ```bash
   cd coredent-api
   ```

2. **Run the migration script**
   ```bash
   python run_migrations_complete.py
   ```

   Or if you're running remotely via Railway CLI:
   ```bash
   railway run python run_migrations_complete.py
   ```

## What Tables Will Be Created

The migrations will create these new tables:

### Communication Tables
- `reminders` - For patient appointment reminders
- `communication_templates` - Email/SMS templates
- `messages` - Sent message history
- `communication_settings` - SMS/Email provider configuration

### Imaging Tables
- `patient_images` - Patient X-rays and photos
- `image_series` - Grouped imaging sessions

### Insurance Tables
- `insurance_carriers` - Insurance company information
- `patient_insurances` - Patient insurance policies

### Marketing Tables
- `marketing_campaigns` - Marketing campaign tracking

### Document Tables
- `patient_documents` - Patient document storage

### Inventory Tables
- `inventory_items` - Dental supply inventory

### Lab Tables
- `lab_cases` - Dental lab case tracking

### Referral Tables
- `referral_partners` - Specialist referral contacts

## Verify Migrations Completed

After running migrations, you can verify the tables were created:

### Using Railway CLI
```bash
railway run psql $DATABASE_URL -c "\dt"
```

### Or connect directly with a database client
- Use the DATABASE_URL from your Railway dashboard
- Connect with pgAdmin, DBeaver, or any PostgreSQL client
- Run: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';`

## Troubleshooting

### If Migrations Fail

1. **Check DATABASE_URL**
   - Make sure it's set in Railway dashboard
   - Format should be: `postgresql://user:password@host:port/database`

2. **Check Database Connection**
   ```bash
   railway run python -c "import os; from sqlalchemy import create_engine; e = create_engine(os.getenv('DATABASE_URL')); print(e.connect().execute('SELECT 1').fetchone())"
   ```

3. **View Migration Status**
   ```bash
   railway run python -m alembic current
   ```

4. **Force Migration**
   If some tables exist but migrations show as not run:
   ```bash
   railway run python -m alembic stamp head
   ```

### If Tables Already Exist

The migration script uses `CREATE TABLE IF NOT EXISTS` for the fallback, so it's safe to run multiple times.

## Next Steps After Migration

1. **Restart your backend** in Railway dashboard
2. **Test the Communications page** - it should now work with real data
3. **Configure SMS/Email providers** in Settings tab
4. **Test sending reminders** from the Schedule page

## Need Help?

If you encounter any issues:
1. Check the Railway logs: `railway logs`
2. Verify your DATABASE_URL is correct
3. Make sure all required tables exist in the database