# 🔑 Reset Admin Password

## Problem
Login returns "Incorrect email or password" - the password hash in the database doesn't match "Admin123!".

## Solution Options

### Option 1: Create New Admin User (Easiest)

Run the create user script again with the EXTERNAL Railway PostgreSQL URL:

```bash
python create_test_user_simple.py
```

When prompted, use the EXTERNAL URL from Railway dashboard:
- Go to Railway → PostgreSQL service → Connect tab
- Copy the "Public Network" URL (starts with `postgresql://postgres:...@caboose.proxy.rlwy.net:...`)

The script will fail with "duplicate key" error, which is expected.

### Option 2: Delete and Recreate Admin User

1. Connect to Railway PostgreSQL using a database client (like DBeaver, pgAdmin, or psql)

2. Delete the existing admin user:
```sql
DELETE FROM users WHERE email = 'admin@coredent.com';
```

3. Run the create user script again:
```bash
python create_test_user_simple.py
```

### Option 3: Update Password Hash Directly

If you have database access, update the password hash:

```sql
UPDATE users 
SET password_hash = '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBBkqq8Kj7KqkL1p8T9m.Yvva'
WHERE email = 'admin@coredent.com';
```

This hash corresponds to password: `Admin123!`

### Option 4: Use Different Credentials

The admin user might have been created with different credentials. Try:
- Email: `admin@coredent.com`
- Password: Try common variations like:
  - `admin123`
  - `Admin@123`
  - `password`
  - `admin`

## Verify It Works

After resetting, test the login:

```bash
python test_login_api.py
```

You should see "✅ Login successful!" instead of 401 error.

## Why This Happened

The password hash in the database doesn't match the bcrypt hash for "Admin123!". This could happen if:
1. The user was created with a different password
2. The password hashing algorithm changed
3. The database was reset/migrated without preserving the correct hash

---

**Recommended**: Use Option 2 (delete and recreate) for a clean slate.
