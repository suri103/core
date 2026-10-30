# ⚡ Create Test User - Quick Steps

## What You Need

1. Your Railway PostgreSQL connection string
2. Python installed
3. The `create_test_user.py` script (already created)

## Get Connection String (2 minutes)

1. Go to: https://railway.app/project/practical-dream
2. Click **PostgreSQL** service
3. Look for **Connect** or **Variables** tab
4. Copy the connection string that looks like:
   ```
   postgresql://username:password@host:port/database
   ```

## Run Script (1 minute)

```bash
python create_test_user.py
```

When prompted, paste your connection string.

## What Happens

✅ Script creates:
- Practice: "Demo Dental Practice"
- Admin user: admin@coredent.com
- Password: Admin123!

## Login to Frontend

1. Go to: https://heartfelt-benevolence-production-ba39.up.railway.app
2. Email: `admin@coredent.com`
3. Password: `Admin123!`
4. Click Login

## Done!

You're now logged in and can test the application.

---

## If Script Fails

### Error: "Connection refused"
- Check connection string is correct
- Make sure PostgreSQL service is running

### Error: "Authentication failed"
- Check username/password in connection string

### Error: "Tables don't exist"
- Migrations haven't been run
- Need to run: `cd coredent-api && alembic upgrade head`

---

## Need Help?

See `🔗_GET_DATABASE_URL.md` for detailed instructions.
