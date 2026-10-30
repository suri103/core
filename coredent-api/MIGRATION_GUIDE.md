# Database Migration Guide - CoreDent PMS

## Overview

This guide covers database migrations for both **Supabase** and **self-hosted PostgreSQL** deployments.

## Migration Files

### Primary Migration
- **File:** `alembic/versions/20260318_1311_001_initial_initial_migration_create_all_tables.py`
- **Purpose:** Creates all 50+ tables required for CoreDent PMS
- **Compatible with:** PostgreSQL 12+, Supabase, any PostgreSQL database

### Tables Created (50+)
- `practices` - Dental practice information
- `users` - Staff and provider accounts
- `patients` - Patient records
- `appointments` - Appointment scheduling
- `treatment_plans` - Treatment planning
- `treatment_procedures` - Individual procedures
- `invoices` - Billing invoices
- `payments` - Payment records
- `insurance_carriers` - Insurance companies
- `patient_insurances` - Patient insurance policies
- `insurance_claims` - Insurance claims
- `inventory_items` - Supply inventory
- `inventory_transactions` - Stock movements
- `labs` - Dental lab information
- `lab_cases` - Lab orders
- `referrals` - Patient referrals
- `documents` - Document management
- `document_signatures` - E-signatures
- `patient_images` - X-rays and photos
- `campaigns` - Marketing campaigns
- `conversations` - Patient communications
- `booking_pages` - Online booking configuration
- `online_bookings` - Online appointment requests
- And more...

---

## Option 1: Supabase Migration

### Prerequisites
1. Create Supabase project at [supabase.com](https://supabase.com)
2. Get your database connection string from Settings → Database

### Step 1: Update Environment
```bash
# coredent-api/.env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Step 2: Install Dependencies
```bash
cd coredent-api
pip install -r requirements.txt
```

### Step 3: Run Migration
```bash
# Option A: Using Alembic (Recommended)
alembic upgrade head

# Option B: Using Python script
python supabase_migration.py
```

### Step 4: Verify
```bash
# Check if tables exist
python -c "
from app.core.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Found {len(tables)} tables')
for table in tables:
    print(f'  - {table}')
"
```

---

## Option 2: Self-Hosted PostgreSQL (Docker)

### Prerequisites
- Docker and Docker Compose installed

### Step 1: Start PostgreSQL
```bash
cd coredent-api
docker-compose up -d
```

This starts:
- PostgreSQL 15 on port 5432
- Redis on port 6379 (optional, for caching)

### Step 2: Update Environment
```bash
# coredent-api/.env
DATABASE_URL=postgresql://coredent:coredent123@localhost:5432/coredent_db
```

### Step 3: Run Migration
```bash
alembic upgrade head
```

### Step 4: Verify
```bash
docker exec -it coredent-postgres psql -U coredent -d coredent_db -c "\dt"
```

---

## Option 3: Self-Hosted PostgreSQL (Cloud Server)

### Prerequisites
- PostgreSQL 12+ installed on server
- Database created: `coredent_db`
- User created with permissions

### Step 1: Create Database
```sql
-- Connect as postgres user
CREATE DATABASE coredent_db;
CREATE USER coredent WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE coredent_db TO coredent;
```

### Step 2: Update Environment
```bash
# coredent-api/.env
DATABASE_URL=postgresql://coredent:your-secure-password@your-server-ip:5432/coredent_db
```

### Step 3: Run Migration
```bash
alembic upgrade head
```

---

## Migration Commands Reference

### Alembic Commands
```bash
# Run all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current migration status
alembic current

# Show migration history
alembic history

# Create new migration (auto-detect changes)
alembic revision --autogenerate -m "description"

# Create empty migration
alembic revision -m "description"
```

### Python Script Commands
```bash
# Test database connection
python supabase_migration.py

# The script will:
# 1. Test connection
# 2. Create extensions (uuid-ossp, pgcrypto, pg_trgm)
# 3. Run migrations
# 4. Setup Row Level Security (RLS)
# 5. Check for admin user
```

---

## Troubleshooting

### Issue: "relation already exists"
**Solution:** Migration already ran. Check status:
```bash
alembic current
```

### Issue: "permission denied"
**Solution:** Grant permissions:
```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO coredent;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO coredent;
```

### Issue: "extension uuid-ossp does not exist"
**Solution:** Create extension as superuser:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Issue: Connection timeout
**Solution:** Check:
1. Database is running
2. Firewall allows port 5432
3. Connection string is correct
4. SSL mode (Supabase requires SSL)

---

## Security Considerations

### Row Level Security (RLS)
After migration, enable RLS for HIPAA compliance:
```sql
-- Enable RLS on sensitive tables
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE treatment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_images ENABLE ROW LEVEL SECURITY;

-- Create policies (example)
CREATE POLICY tenant_isolation ON patients
  USING (practice_id = current_setting('app.current_practice_id')::uuid);
```

### Backup Strategy
```bash
# Backup database
pg_dump -h [HOST] -U [USER] -d [DATABASE] > backup_$(date +%Y%m%d).sql

# Restore database
psql -h [HOST] -U [USER] -d [DATABASE] < backup_20260321.sql
```

---

## Migration Between Environments

### Export from Supabase
```bash
pg_dump -h db.[PROJECT-REF].supabase.co -U postgres -d postgres > supabase_backup.sql
```

### Import to Self-Hosted
```bash
psql -h localhost -U coredent -d coredent_db < supabase_backup.sql
```

### Export from Self-Hosted
```bash
pg_dump -h localhost -U coredent -d coredent_db > selfhosted_backup.sql
```

### Import to Supabase
```bash
psql -h db.[PROJECT-REF].supabase.co -U postgres -d postgres < selfhosted_backup.sql
```

---

## Best Practices

1. **Always backup before migration**
2. **Test migrations in development first**
3. **Use Alembic for version control**
4. **Document schema changes**
5. **Monitor migration execution time**
6. **Verify data integrity after migration**

---

## Support

For migration issues:
1. Check logs: `alembic history --verbose`
2. Verify connection: `python -c "from app.core.database import engine; print(engine.connect())"`
3. Check PostgreSQL version: `SELECT version();`