# Create Test User via Railway SQL

Since the Python script needs environment variables, we'll create the user directly in the database.

## Steps:

### 1. Go to Railway Dashboard
- URL: https://railway.app/project/practical-dream
- Click on **PostgreSQL** service

### 2. Click "Connect" or "Data" Tab
- Look for a way to access the database
- You should see connection details or a query editor

### 3. Run This SQL Query

```sql
-- Create practice first
INSERT INTO practice (
  id, name, email, phone, 
  address_street, address_city, address_state, address_zip,
  timezone, currency, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'Demo Dental Practice',
  'info@demodental.com',
  '555-0123',
  '123 Main Street',
  'Springfield',
  'IL',
  '62701',
  'America/Chicago',
  'USD',
  NOW(),
  NOW()
) RETURNING id;
```

Copy the returned ID, then run:

```sql
-- Create admin user (replace PRACTICE_ID with the ID from above)
INSERT INTO "user" (
  id, email, password_hash, first_name, last_name,
  role, practice_id, is_active, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'admin@coredent.com',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva',
  'Admin',
  'User',
  'owner',
  'PRACTICE_ID',
  true,
  NOW(),
  NOW()
);
```

**Note**: The password hash is for "Admin123!"

### 4. Test Login
- Email: `admin@coredent.com`
- Password: `Admin123!`

## Alternative: Use Railway CLI

If you have Railway CLI installed:

```bash
railway connect postgresql
```

Then paste the SQL queries above.

## If You Don't Have Database Access

You can create the user through the API once it's running, but you'll need to:
1. Create a registration endpoint
2. Or use a database GUI tool
3. Or ask me to create a simpler script
