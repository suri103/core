# 🗄️ Run Database Migrations on Railway

## Why Migrations Haven't Run Yet

The backend deployment is failing (can't find `requirements.txt`), so the automatic migration command in the Dockerfile hasn't executed. We need to run migrations manually.

## Option 1: Run Migrations Locally (RECOMMENDED)

### Step 1: Get Railway Database URL
1. Go to https://railway.app
2. Select your **PostgreSQL** service (not the backend service)
3. Click **Variables** tab
4. Copy the **DATABASE_URL** value
   - It looks like: `postgresql://postgres:password@host.railway.internal:5432/railway`

### Step 2: Install Dependencies (if needed)
```bash
cd coredent-api
pip install alembic psycopg2-binary sqlalchemy
```

### Step 3: Run Migration Script
```bash
# From the root directory
python run_migrations_on_railway.py "postgresql://your-database-url-here"
```

Replace `"postgresql://your-database-url-here"` with the actual DATABASE_URL from Railway.

### Expected Output
```
================================================================================
🚀 Running Alembic Migrations on Railway Database
================================================================================
📁 Working directory: D:\coredentist\coredent-api
🗄️  Database: host.railway.internal:5432/railway
================================================================================

📊 Checking current database revision...
⬆️  Upgrading to head...
✅ Migration complete!

📋 Applied migrations:
  1. 20260318_1311 - Initial migration (all tables)
  2. 20260407_1130 - GST fields for invoices
  3. 20260407_1200 - Performance indexes
  4. 20260407_1730 - Subscription tables
  5. 20260408_1800 - Account lockout fields
  6. 20260408_1830 - Email verification fields

🎉 Your Railway database is now up to date!
```

## Option 2: Fix Backend First, Then Auto-Migrate

If you prefer to wait for the backend to deploy:

1. Fix Railway deployment (set Root Directory to `coredent-api`)
2. Backend will automatically run migrations on startup
3. Check logs for: `alembic upgrade head`

## Option 3: Use Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run migrations
railway run python run_migrations_on_railway.py $DATABASE_URL
```

## Verify Migrations

After running migrations, verify tables exist:

### Using psql:
```bash
psql "postgresql://your-database-url" -c "\dt"
```

### Expected Tables (50+ tables):
- users
- practices
- patients
- appointments
- invoices
- payments
- subscriptions
- insurance_claims
- treatments
- imaging_studies
- inventory_items
- lab_orders
- referrals
- communications
- documents
- marketing_campaigns
- audit_logs
- ... and many more

## What Each Migration Does

### 1. Initial Migration (20260318_1311)
Creates all core tables:
- User management (users, roles, permissions)
- Practice management (practices, locations, chairs)
- Patient management (patients, medical history, allergies)
- Appointments (appointments, schedules, availability)
- Billing (invoices, payments, insurance)
- Clinical (treatments, procedures, notes)
- And 40+ more tables

### 2. GST Fields (20260407_1130)
Adds Indian tax fields to invoices:
- gst_number
- gst_rate
- cgst_amount
- sgst_amount
- igst_amount

### 3. Performance Indexes (20260407_1200)
Adds 40+ database indexes for:
- Faster patient searches
- Faster appointment queries
- Faster billing lookups
- Optimized JOIN operations

### 4. Subscription Tables (20260407_1730)
Adds SaaS subscription management:
- subscriptions table
- subscription_plans table
- subscription_usage table
- Payment integration (Stripe/Razorpay)

### 5. Account Lockout (20260408_1800)
Adds security fields to users table:
- failed_login_attempts
- account_locked_until
- last_failed_login

### 6. Email Verification (20260408_1830)
Adds email verification to users table:
- is_email_verified
- email_verification_token
- email_verification_sent_at

## Troubleshooting

### Error: "relation already exists"
- Some tables already exist
- Safe to ignore if migrations complete
- Or drop all tables and re-run

### Error: "connection refused"
- Check DATABASE_URL is correct
- Verify Railway database is running
- Check network connectivity

### Error: "alembic not installed"
```bash
pip install alembic psycopg2-binary sqlalchemy
```

---

**Status**: ⏳ Waiting for you to run migrations  
**Time Required**: 2-3 minutes  
**Priority**: 🔴 HIGH - Required before backend can work

**Next Steps**:
1. Get DATABASE_URL from Railway
2. Run migration script
3. Verify tables exist
4. Fix backend deployment
5. Test application
