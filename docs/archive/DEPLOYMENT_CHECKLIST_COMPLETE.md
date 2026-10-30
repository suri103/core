# 🚀 CoreDent Deployment Checklist - Complete Guide

## Prerequisites

Before deploying, ensure you have:
- Railway.app account with project set up
- Supabase/PostgreSQL database provisioned
- Custom domain (optional but recommended)
- Stripe account for payments
- SendGrid/AWS SES account for emails

---

## 1. Run Database Migrations

### Option A: Via Railway Dashboard
1. Go to your Railway project → Backend service
2. Click "Shell" tab
3. Run:
```bash
alembic upgrade head
```

### Option B: Via Python Script
```bash
cd coredent-api
python run_migrations_railway.py
```

### Option C: Manual SQL (if migrations fail)
```bash
# Connect to your PostgreSQL database
psql -h <host> -U <user> -d <database>

# Run the migration SQL directly
\i coredent-api/alembic/versions/20260407_1730_add_subscription_tables.py
```

### Verify Migrations
```bash
alembic current
# Should show: 20260407_1730 (head)
```

---

## 2. Configure Stripe API Keys

### Get Stripe Keys
1. Go to https://dashboard.stripe.com/apikeys
2. Copy your **Publishable Key** and **Secret Key**
3. For production, use the live keys (not test keys)

### Add to Railway Environment Variables
In Railway Dashboard → Backend → Variables:
```
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

### Create Stripe Products
```bash
# After deployment, use the API to create subscription plans
curl -X POST https://your-backend-url/subscriptions/plans \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Basic Plan",
    "description": "Essential features for small practices",
    "amount": 49.00,
    "currency": "USD",
    "interval": "monthly",
    "trial_period_days": 14,
    "features": ["Patient Management", "Appointment Scheduling", "Basic Reporting"]
  }'
```

---

## 3. Set Up Stripe Webhook Endpoint

### Create Webhook in Stripe Dashboard
1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter your backend URL: `https://your-backend-url.railway.app/api/v1/subscriptions/webhook`
4. Select events to listen for:
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.trial_will_end`
5. Copy the **Webhook Secret** (whsec_xxx)

### Add Webhook Secret to Railway
```
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

### Test Webhook Locally
```bash
# Install Stripe CLI
stripe listen --forward-to localhost:8000/api/v1/subscriptions/webhook

# Trigger test events
stripe trigger invoice.payment_succeeded
```

---

## 4. Configure Email Service

### Option A: SendGrid
1. Sign up at https://sendgrid.com
2. Create API Key (Full Access)
3. Verify your sender domain

Add to Railway:
```
SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com
EMAIL_PROVIDER=sendgrid
```

### Option B: AWS SES
1. Go to AWS Console → SES
2. Verify your domain/email
3. Create SMTP credentials

Add to Railway:
```
SES_SMTP_USERNAME=xxxxxxxxxxxxx
SES_SMTP_PASSWORD=xxxxxxxxxxxxx
SES_REGION=us-east-1
EMAIL_FROM=noreply@yourdomain.com
EMAIL_PROVIDER=ses
```

### Test Email Configuration
```bash
# After deployment, test email sending
curl -X POST https://your-backend-url.railway.app/api/v1/test-email \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

## 5. Verify CORS Allowed Origins

### Check Backend Configuration
In `coredent-api/app/core/config.py`, ensure:
```python
ALLOWED_ORIGINS: str = "https://your-frontend-domain.com,https://your-custom-domain.com"
```

### Add to Railway Environment Variables
```
ALLOWED_ORIGINS=https://your-frontend.railway.app,https://your-custom-domain.com
```

### Test CORS
```bash
curl -H "Origin: https://your-frontend-domain.com" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS https://your-backend-url.railway.app/api/v1/health
# Should return Access-Control-Allow-Origin header
```

---

## 6. Set Production Environment Variables

### Required Backend Variables (Railway)
```
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-super-secret-key-min-32-chars
ALLOWED_ORIGINS=https://your-frontend-domain.com
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
SENDGRID_API_KEY=SG.xxx (or SES credentials)
EMAIL_FROM=noreply@yourdomain.com
REDIS_URL=redis://your-redis-url (if using Redis)
ENCRYPTION_KEY=your-32-byte-encryption-key
ENVIRONMENT=production
```

### Required Frontend Variables
In `coredent-style-main/.env.production`:
```
VITE_API_URL=https://your-backend-url.railway.app
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
```

---

## 7. Run Frontend Build

### Local Build Test
```bash
cd coredent-style-main
npm install
npm run build
# Check for build errors
```

### Fix Common Build Issues
```bash
# If TypeScript errors occur
npm run build -- --no-lint

# If ESLint errors occur
npm run build -- --no-lint --no-typecheck
```

### Deploy Frontend to Railway
1. Push code to GitHub
2. Railway will auto-deploy from the `coredent-style-main` directory
3. Or manually trigger deploy in Railway Dashboard

---

## 8. Deploy Backend and Frontend

### Deploy via Railway
1. Push all changes to GitHub:
```bash
git add .
git commit -m "feat: add subscription system and deployment fixes"
git push origin main
```

2. Railway will auto-deploy both services

### Verify Deployment
```bash
# Check backend health
curl https://your-backend-url.railway.app/api/v1/health

# Check frontend
curl https://your-frontend-url.railway.app

# Check API endpoints
curl https://your-backend-url.railway.app/api/v1/subscriptions/plans
```

### Post-Deployment Verification
1. **Login Test**: Try logging in with admin credentials
2. **API Test**: Test a few API endpoints
3. **Database Test**: Check if migrations ran successfully
4. **Email Test**: Trigger a password reset email
5. **Stripe Test**: Create a test subscription

---

## Quick Commands Reference

### Backend
```bash
# Run migrations
alembic upgrade head

# Check migration status
alembic current

# Rollback last migration
alembic downgrade -1

# Create new migration
alembic revision --autogenerate -m "description"

# Start development server
uvicorn app.main:app --reload

# Run tests
pytest
```

### Frontend
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Run type checking
npm run type-check
```

---

## Troubleshooting

### Migration Fails
```bash
# Check database connection
python -c "from app.core.database import engine; print(engine.url)"

# Stamp current revision (if migrations out of sync)
alembic stamp head
```

### CORS Errors
- Check `ALLOWED_ORIGINS` includes your frontend URL
- Ensure no trailing slashes in origins
- Restart backend after changing env vars

### Stripe Webhook Not Working
- Verify webhook URL is correct: `/api/v1/subscriptions/webhook`
- Check `STRIPE_WEBHOOK_SECRET` matches
- Check Railway logs for errors

### Email Not Sending
- Verify API key is correct
- Check sender domain is verified (SendGrid/SES)
- Check Railway logs for email errors

---

## Next Steps After Deployment

1. **Monitor Logs**: Check Railway logs for errors
2. **Set Up Monitoring**: Configure uptime monitoring (UptimeRobot, Pingdom)
3. **Configure Backups**: Set up automated database backups
4. **Set Up Alerts**: Configure alerts for errors and downtime
5. **Performance Testing**: Run load tests to ensure scalability
6. **Security Audit**: Run security scans on deployed app