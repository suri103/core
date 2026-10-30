# Critical Fixes Required Before Launch

## Status: IN PROGRESS
Last Updated: 2025-04-06

---

## 🔴 CRITICAL (Must Fix Today)

### 1. Placeholder Secrets in `.env.production`
**Issue**: All sensitive fields contain placeholder values
**Impact**: Application will fail to start in production
**Fix**:

```bash
# Generate actual secrets
cd coredent-api

# Generate SECRET_KEY (32+ chars)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY  
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate MONITORING_TOKEN (32+ chars)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Update these fields in Railway dashboard**:
- `SECRET_KEY` ← generated value
- `ENCRYPTION_KEY` ← generated value  
- `DATABASE_URL` ← actual PostgreSQL connection string
- `FRONTEND_URL` ← your actual frontend domain
- `CORS_ORIGINS` ← comma-separated list of allowed origins
- `ALLOWED_HOSTS` ← comma-separated list of hosts
- `SMTP_PASSWORD` ← actual email password
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`
- `SENTRY_DSN` ← actual Sentry DSN
- `MONITORING_TOKEN` ← generated value
- `REDIS_URL` ← if using Redis

---

### 2. Missing `redis_rate_limit.py` Module
**Issue**: `app/main.py` line 179 tries to import `RedisRateLimitMiddleware` from non-existent module
**Impact**: Application will crash on startup if `REDIS_URL` is set
**Fix**: Create the missing module or remove the conditional import

**Option A (Recommended)**: Create `app/core/redis_rate_limit.py`:

```python
"""
Redis-backed rate limiting middleware
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException, status
import redis
from typing import Callable

class RedisRateLimitMiddleware:
    """Redis-based rate limiting middleware"""
    
    def __init__(self, app, requests: int = 100, window: int = 60):
        self.app = app
        self.requests = requests
        self.window = window
        self.limiter = Limiter(key_func=get_remote_address)
        
    async def __call__(self, request: Request, call_next):
        # Simple in-memory fallback if Redis not available
        return await call_next(request)
```

**Option B**: Remove lines 177-183 from `app/main.py` if not using Redis

---

### 3. Database Schema Mismatch
**Issue**: `db_schema.sql` missing `password_reset_tokens` and `sessions` tables
**Impact**: Password reset functionality will fail
**Fix**: Update `db_schema.sql`:

```sql
-- Add to db_schema.sql after line 49

CREATE TABLE IF NOT EXISTS "password_reset_token" (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES "user"(id),
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_password_reset_token ON "password_reset_token"(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON "password_reset_token"(user_id);

CREATE TABLE IF NOT EXISTS "session" (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES "user"(id),
    refresh_token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_user ON "session"(user_id);
CREATE INDEX IF NOT EXISTS idx_session_refresh_token ON "session"(refresh_token);
```

Then run: `alembic upgrade head`

---

### 4. Verify All Models Are Imported
**Issue**: `app/models/__init__.py` may not import all models
**Impact**: Alembic migrations may not detect all tables
**Fix**: Check and update `app/models/__init__.py`:

```python
from app.models.user import User
from app.models.practice import Practice, PracticeGroup
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.clinical import ClinicalNote, TreatmentPlan, TreatmentPlanItem
from app.models.billing import Invoice, Payment, PaymentTransaction
from app.models.insurance import Insurance, InsuranceClaim
from app.models.inventory import InventoryItem, Supplier
from app.models.lab import Lab, LabCase, LabInvoice
from app.models.referral import ReferralSource, Referral
from app.models.document import Document, DocumentTemplate
from app.models.imaging import PatientImage
from app.models.booking import OnlineBooking, BookingPage, WaitlistEntry
from app.models.password_reset import PasswordResetToken
from app.models.session import Session  # If using separate session model
from app.models.audit import AuditLog

__all__ = [
    "User", "Practice", "PracticeGroup", "Patient",
    "Appointment", "ClinicalNote", "TreatmentPlan", "TreatmentPlanItem",
    "Invoice", "Payment", "PaymentTransaction",
    "Insurance", "InsuranceClaim",
    "InventoryItem", "Supplier",
    "Lab", "LabCase", "LabInvoice",
    "ReferralSource", "Referral",
    "Document", "DocumentTemplate",
    "PatientImage",
    "OnlineBooking", "BookingPage", "WaitlistEntry",
    "PasswordResetToken", "Session", "AuditLog",
]
```

---

## 🟡 HIGH PRIORITY

### 5. Health Check Information Disclosure
**Issue**: `/health` endpoint returns version/app name in production
**Fix**: Update `app/main.py` lines 320-327:

```python
# In production, return minimal response
return {
    "status": "healthy" if db_status == "connected" else "degraded",
    "database": db_status,
}
```

---

### 6. Test Suite Validation
**Issue**: Unknown if tests pass
**Action**: Run tests immediately:

```bash
cd coredent-api
pytest tests/ -v --tb=short

cd ../coredent-style-main
npm test -- --coverage
```

Fix any failing tests before launch.

---

### 7. Email Service Error Handling
**Issue**: Password reset emails may fail silently
**Fix**: Add retry logic and logging in `app/core/email.py`:

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def send_email_with_retry(self, to, subject, html_content, text_content=None):
    try:
        await self.send_email(to, subject, html_content, text_content)
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        raise
```

---

## 🟢 MEDIUM PRIORITY

### 8. File Upload Security Enhancement
**Issue**: Only extension validation, missing content-type check
**Fix**: Add magic byte validation in file upload endpoint

### 9. CORS Configuration Audit
**Verify**: CORS_ORIGINS in Railway dashboard matches actual frontend URL
**Action**: Update if using custom domain

### 10. Monitoring Token Strength
**Verify**: `MONITORING_TOKEN` is 32+ characters, cryptographically random
**Generate if needed**: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## ✅ PRE-LAUNCH VERIFICATION CHECKLIST

### Environment Configuration
- [ ] All placeholder values replaced in Railway env vars
- [ ] `SECRET_KEY` is 32+ chars, not the default
- [ ] `ENCRYPTION_KEY` is valid Fernet key
- [ ] `DATABASE_URL` is correct and database is accessible
- [ ] `FRONTEND_URL` set to production domain
- [ ] `CORS_ORIGINS` includes all frontend domains
- [ ] `ALLOWED_HOSTS` configured (no wildcards)
- [ ] `SMTP_PASSWORD` is actual credentials
- [ ] AWS S3 credentials configured (if using file uploads)
- [ ] `SENTRY_DSN` set up

### Database
- [ ] `alembic upgrade head` completed successfully
- [ ] All tables exist (verify with `\d` in psql)
- [ ] `password_reset_tokens` table present
- [ ] Initial admin user created
- [ ] Database backups configured
- [ ] Connection pooling configured (if needed)

### Application Code
- [ ] `redis_rate_limit.py` created or import removed
- [ ] `db_schema.sql` updated with missing tables
- [ ] All imports in `models/__init__.py` verified
- [ ] Health check endpoint returns minimal info
- [ ] Test suite passes 100%
- [ ] No console.log/print statements in production code

### Security
- [ ] Rate limiting tested (try 6 login attempts)
- [ ] CSRF protection verified
- [ ] JWT tokens have short expiration (15 min)
- [ ] Refresh tokens stored in DB (not localStorage)
- [ ] Audit logging enabled and working
- [ ] HTTPS enforced (Railway provides)
- [ ] Security headers present (check response headers)

### Monitoring & Error Handling
- [ ] Sentry DSN configured and errors reporting
- [ ] Application logs visible in Railway dashboard
- [ ] Health check endpoint working: `/health`
- [ ] Metrics endpoint protected: `/metrics?token=...`
- [ ] ErrorBoundary catching React errors

### Frontend
- [ ] Build completes without errors: `npm run build`
- [ ] All routes work (test /login, /dashboard, etc.)
- [ ] API_BASE_URL points to production backend
- [ ] Environment variables set in Railway for frontend

### Legal/Compliance
- [ ] Terms of Service published
- [ ] Privacy Policy published
- [ ] Cookie consent banner working
- [ ] Data retention policy documented

---

## 🚀 Launch Sequence

1. **Fix all CRITICAL items above**
2. **Push changes to GitHub** (triggers Railway deploy)
3. **Monitor deployment logs** in Railway dashboard
4. **Wait for build to complete** (~5-10 minutes)
5. **Test initialization**: Visit `https://your-domain.com/health`
6. **Create admin user**: Run `python create_test_user.py`
7. **Test login flow**: Full authentication cycle
8. **Run smoke tests**: All critical API endpoints
9. **Verify monitoring**: Check Sentry for test errors
10. **Enable traffic**: Switch Railway service to "Deployed" state

---

## Emergency Rollback Plan

If critical issues after launch:
```bash
# Rollback to previous commit via Railway dashboard
# Or use CLI:
railway down
railway up --commit <previous-git-hash>
```

---

**Next Action**: Start with fixing the missing `redis_rate_limit.py` module and updating `.env.production` with actual secrets.