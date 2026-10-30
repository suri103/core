# 🚀 Supabase Setup Guide

## Connecting CoreDent PMS to Supabase

**Supabase Benefits:**
- ✅ Fully managed PostgreSQL database
- ✅ Built-in authentication (JWT, OAuth)
- ✅ Real-time subscriptions
- ✅ Row Level Security (RLS)
- ✅ Automatic backups
- ✅ Easy scaling
- ✅ HIPAA compliant (Business plan)

---

## 📋 STEP 1: Create Supabase Project

### 1. Sign up for Supabase
- Go to [supabase.com](https://supabase.com)
- Sign up with GitHub, GitLab, or email
- It's free to start (up to 2 projects)

### 2. Create New Project
1. Click "New Project"
2. **Project Name:** `coredent-pms`
3. **Database Password:** Create a strong password (save it!)
4. **Region:** Choose closest to your users (US East for US)
5. **Pricing Plan:** Free (upgrade to Pro for production)

### 3. Get Connection Details
After project creation, go to:
- **Settings → Database → Connection string**
- Copy the **Connection URI**

**Format:** `postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres`

---

## 🔧 STEP 2: Configure Environment Variables

### Update `coredent-api/.env`:

```bash
# Database - Supabase Configuration
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# Supabase Connection Details
SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
SUPABASE_ANON_KEY=[YOUR-ANON-KEY]
SUPABASE_SERVICE_ROLE_KEY=[YOUR-SERVICE-ROLE-KEY]
```

### Get Your Keys:
1. Go to **Project Settings → API**
2. Copy:
   - **URL:** `https://[project-ref].supabase.co`
   - **anon public:** Your anon key
   - **service_role secret:** Your service role key

---

## 🗄️ STEP 3: Run Database Migrations

### Option A: Using Supabase CLI (Recommended)

1. **Install Supabase CLI:**
   ```bash
   # Windows (PowerShell)
   winget install supabase.supabase-cli

   # macOS
   brew install supabase/tap/supabase

   # Linux
   curl -s https://cli.supabase.com/install.sh | sh
   ```

2. **Login to Supabase:**
   ```bash
   supabase login
   ```

3. **Link your project:**
   ```bash
   cd coredent-api
   supabase link --project-ref [YOUR-PROJECT-REF]
   ```

4. **Run migrations:**
   ```bash
   supabase db push
   ```

### Option B: Using Python Script

1. **Install dependencies:**
   ```bash
   cd coredent-api
   pip install asyncpg alembic
   ```

2. **Run migration:**
   ```bash
   # Update alembic.ini with Supabase URL
   # Then run:
   alembic upgrade head
   ```

### Option C: Using Supabase Dashboard

1. Go to **SQL Editor**
2. Create a new query
3. Run the SQL from `coredent-api/db_schema.sql`

---

## 🔒 STEP 4: Configure Row Level Security (RLS)

### Enable RLS on Tables:

Run this SQL in Supabase SQL Editor:

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE practices ENABLE ROW LEVEL SECURITY;
ALTER TABLE insurance_carriers ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_insurances ENABLE ROW LEVEL SECURITY;
ALTER TABLE insurance_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_images ENABLE ROW LEVEL SECURITY;

-- Create policies for users table
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Practice admins can view all users" ON users
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM users AS admin
      WHERE admin.id = auth.uid()
      AND admin.practice_id = users.practice_id
      AND admin.role IN ('owner', 'admin')
    )
  );

-- Create policies for patients table
CREATE POLICY "Practice staff can view patients" ON patients
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.practice_id = patients.practice_id
    )
  );

CREATE POLICY "Practice staff can insert patients" ON patients
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.practice_id = patients.practice_id
    )
  );
```

---

## 🔐 STEP 5: Configure Authentication

### Option A: Use Supabase Auth (Recommended)

1. **Enable Email Auth:**
   - Go to **Authentication → Providers**
   - Enable "Email"
   - Configure email templates

2. **Configure JWT Settings:**
   - Go to **Authentication → Settings**
   - Set JWT expiry: 15 minutes (access), 7 days (refresh)
   - Enable "Enable captcha protection"

3. **Update Backend to Use Supabase Auth:**

Modify `app/core/security.py`:

```python
from supabase import create_client, Client
import os

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def verify_supabase_token(token: str):
    """Verify JWT token with Supabase"""
    try:
        user = supabase.auth.get_user(token)
        return user
    except:
        return None
```

### Option B: Keep Custom Auth (Current)

Your current JWT auth will work with Supabase. Just update the database connection.

---

## 📊 STEP 6: Set Up Database Extensions

Run in SQL Editor:

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Enable full-text search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

---

## 🚀 STEP 7: Deploy to Production

### 1. Update Production Environment:

```bash
# Production .env
DATABASE_URL=postgresql://postgres:[PROD-PASSWORD]@db.[PROD-PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://[PROD-PROJECT-REF].supabase.co
SUPABASE_ANON_KEY=[PROD-ANON-KEY]
SUPABASE_SERVICE_ROLE_KEY=[PROD-SERVICE-ROLE-KEY]
```

### 2. Set Up Backups:
- Go to **Settings → Database → Backups**
- Enable daily backups
- Set retention period (7-30 days)

### 3. Configure Monitoring:
- Go to **Settings → Database → Monitoring**
- Set up alerts for:
  - High CPU usage (>80%)
  - High memory usage (>90%)
  - Slow queries (>1000ms)

---

## 🔧 STEP 8: Connect Frontend to Supabase

### Option A: Use Supabase JS Client

1. **Install Supabase JS:**
   ```bash
   cd coredent-style-main
   npm install @supabase/supabase-js
   ```

2. **Create Supabase client:**
   ```typescript
   // src/lib/supabase.ts
   import { createClient } from '@supabase/supabase-js'

   const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
   const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

   export const supabase = createClient(supabaseUrl, supabaseAnonKey)
   ```

3. **Update frontend .env:**
   ```bash
   VITE_SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
   VITE_SUPABASE_ANON_KEY=[YOUR-ANON-KEY]
   ```

### Option B: Keep Current API (Recommended)

Your current FastAPI backend will handle all database operations. Frontend only needs to talk to your API.

---

## 💰 STEP 9: Pricing & Scaling

### Free Plan (Development)
- **Database:** 500MB storage
- **Bandwidth:** 2GB/month
- **Auth:** 50,000 monthly active users
- **Realtime:** 2 concurrent connections
- **Perfect for:** Development, testing, small MVP

### Pro Plan ($25/month) - Recommended for Production
- **Database:** 8GB storage + 250GB additional
- **Bandwidth:** 50GB/month
- **Auth:** 100,000 monthly active users
- **Realtime:** 100 concurrent connections
- **Backups:** 7 day retention
- **Perfect for:** Small to medium practices

### Enterprise Plan (Custom) - HIPAA Compliant
- **HIPAA compliance**
- **SOC 2 Type II**
- **Custom SLAs**
- **Dedicated support**
- **Perfect for:** Healthcare applications

---

## 🛡️ STEP 10: Security Best Practices

### 1. Database Security:
```sql
-- Disable public access
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Create read-only role for analytics
CREATE ROLE read_only;
GRANT CONNECT ON DATABASE postgres TO read_only;
GRANT USAGE ON SCHEMA public TO read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only;
```

### 2. Network Security:
- Enable **SSL enforcement**
- Set up **IP allowlisting**
- Enable **network restrictions**

### 3. Audit Logging:
```sql
-- Enable audit logging
CREATE EXTENSION IF NOT EXISTS "pgaudit";
ALTER DATABASE postgres SET pgaudit.log = 'all';
ALTER DATABASE postgres SET pgaudit.log_relation = 'on';
```

---

## 🔍 STEP 11: Testing Connection

### Test Database Connection:
```python
# test_connection.py
import asyncpg
import asyncio
import os

async def test_connection():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    version = await conn.fetchval('SELECT version()')
    print(f"Connected to: {version}")
    await conn.close()

asyncio.run(test_connection())
```

### Test Supabase Auth:
```python
# test_auth.py
from supabase import create_client
import os

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_ANON_KEY')
)

# Test auth
response = supabase.auth.sign_in_with_password({
    "email": "test@example.com",
    "password": "password123"
})
print(f"Auth test: {response}")
```

---

## 🚨 TROUBLESHOOTING

### Common Issues:

1. **Connection refused:**
   - Check firewall settings
   - Verify database URL
   - Ensure SSL is enabled

2. **Migration errors:**
   - Check SQL syntax
   - Verify extensions are enabled
   - Check user permissions

3. **RLS blocking queries:**
   - Review RLS policies
   - Check user role/permissions
   - Test with service role key

4. **Performance issues:**
   - Add database indexes
   - Enable connection pooling
   - Monitor query performance

### Support Resources:
- [Supabase Documentation](https://supabase.com/docs)
- [Discord Community](https://discord.supabase.com)
- [GitHub Issues](https://github.com/supabase/supabase/issues)

---

## ✅ COMPLETION CHECKLIST

- [ ] Created Supabase project
- [ ] Updated `.env` with Supabase credentials
- [ ] Ran database migrations
- [ ] Configured RLS policies
- [ ] Set up authentication
- [ ] Enabled required extensions
- [ ] Configured backups
- [ ] Tested connection
- [ ] Updated frontend .env
- [ ] Set up monitoring

---

## 🎉 YOU'RE READY!

### Benefits of Using Supabase:

1. **✅ Fully Managed:** No database administration
2. **✅ Scalable:** From free to enterprise
3. **✅ Secure:** Built-in RLS, SSL, backups
4. **✅ Real-time:** Live updates for appointments
5. **✅ Cost-effective:** Starts free, scales predictably
6. **✅ HIPAA Ready:** Enterprise plan available

### Next Steps:
1. Complete the checklist above
2. Test with a few sample practices
3. Monitor performance for 1 week
4. Scale up as needed

**Your CoreDent PMS is now Supabase-ready!** 🚀