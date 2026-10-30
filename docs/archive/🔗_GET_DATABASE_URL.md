# 🔗 Get Database Connection String from Railway

## Steps to Get PostgreSQL URL

### 1. Go to Railway Dashboard
- URL: https://railway.app/project/practical-dream

### 2. Click on PostgreSQL Service
- You should see a "PostgreSQL" service in your project
- Click on it

### 3. Find Connection String

Look for one of these tabs/sections:
- **Connect** tab
- **Data** tab
- **Variables** tab
- **Connection** section

### 4. Copy the Connection String

You should see something like:
```
postgresql://username:password@host:port/database
```

Example:
```
postgresql://postgres:abc123@containers-us-west-123.railway.app:5432/railway
```

### 5. Run the Script

```bash
python create_test_user.py
```

When prompted, paste the connection string:
```
postgresql://postgres:abc123@containers-us-west-123.railway.app:5432/railway
```

### 6. Script Creates User

The script will:
1. Connect to your database
2. Create a practice
3. Create an admin user
4. Show you the credentials

### 7. Login

Use these credentials:
- Email: `admin@coredent.com`
- Password: `Admin123!`

---

## If You Can't Find Connection String

### Option A: Check Environment Variables
1. Go to PostgreSQL service
2. Click **Variables** tab
3. Look for `DATABASE_URL`
4. Copy the value

### Option B: Use Railway CLI
```bash
railway link
railway connect postgresql
```

This will open a direct connection to the database.

### Option C: Check Backend Service
1. Go to **coredentist** (backend) service
2. Click **Variables** tab
3. Look for `DATABASE_URL`
4. Copy it

---

## Troubleshooting

### "Connection refused"
- Check that the host is correct
- Make sure PostgreSQL service is running
- Verify network connectivity

### "Authentication failed"
- Check username and password
- Make sure they're correct in the connection string

### "Database does not exist"
- Check the database name at the end of the URL
- Make sure migrations have been run

### "Tables don't exist"
- Run migrations first:
  ```bash
  cd coredent-api
  alembic upgrade head
  ```

---

## Next Steps

Once the user is created:
1. Go to frontend: https://heartfelt-benevolence-production-ba39.up.railway.app
2. Login with admin@coredent.com / Admin123!
3. Test the application
