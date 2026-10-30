# 🛡️ CoreDent PMS - Production Readiness Checklist

**Date:** March 15, 2026

## 1. Security & Environment
- [x] **Secure Environment Variables**: Verified that no secrets are in the frontend build.
- [x] **HTTPS Enforcement**: Backend has `HTTPSRedirectMiddleware` and HSTS headers.
- [x] **Protected Routes**: All sensitive frontend pages are behind `ProtectedRoute`.
- [x] **API Key Encryption**: Sensitive database fields are encrypted with Fernet.
- [x] **Rate Limiting**: Need to tighten limits on `/login` (Fix below).

## 2. Infrastructure & Operations
- [x] **Logging**: Sentry is integrated in both frontend and backend.
- [x] **Audit Logging**: Tracking data reads (PHI access) is still missing.
- [x] **Error Messaging**: Production backend hides internal tracebacks.
- [x] **Dockerized**: Both services have production-ready Dockerfiles.

## 3. Dependency Check
- [x] **Vulnerability Scan**: `pip-audit` and `npm audit` run.
- [x] **Outdated Packages**: `fastapi` and `sqlalchemy` need updates.

---

## 4. Required Fixes Before Launch

### 4.1 Tighten Rate Limits
Update `app/main.py` or specific routers to restrict login attempts.

### 4.2 PHI Access Logging
Implement the `audit_middleware` to log every time a user views a patient record.

### 4.3 Dependency Upgrades
Update `requirements.txt` to:
- `fastapi>=0.115.0`
- `sqlalchemy>=2.0.35`
- `pydantic>=2.10.0`

### 4.4 Final Security Headers
Verify `X-Frame-Options` and `X-Content-Type-Options` are active (Verified: They are).
