# 🔍 MULTI-TENANT DATA ISOLATION AUDIT

**Date**: April 13, 2026  
**Status**: ⚠️ **NEEDS VERIFICATION**  
**Priority**: **HIGH** (Required before production launch)

---

## 🎯 What is Multi-Tenant Data Isolation?

In a B2B2C SaaS like CoreDent:
- **You** (CoreDent) → **Dental Practices** → **Their Patients**
- Each dental practice is a **tenant**
- **Critical**: Practice A must NEVER see Practice B's data

**Security Risk**: If isolation fails, one practice could access another's patient records → **HIPAA violation** + **lawsuit**

---

## ✅ Current Multi-Tenant Implementation

### 1. Database Schema (Row-Level Security)

Every table has a `practice_id` column:

```sql
-- Patients table
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    practice_id UUID NOT NULL REFERENCES practices(id),  -- ✅ Tenant isolation
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    -- ...
);

-- Appointments table
CREATE TABLE appointments (
    id UUID PRIMARY KEY,
    practice_id UUID NOT NULL REFERENCES practices(id),  -- ✅ Tenant isolation
    patient_id UUID REFERENCES patients(id),
    -- ...
);
```

### 2. API Security (JWT Token)

Every API request includes `practice_id` in JWT:

```python
# Token payload
{
    "sub": "user_id",
    "role": "dentist",
    "practice_id": "practice_123"  # ✅ Tenant context
}
```

### 3. Query Filtering (Automatic)

All queries filter by `practice_id`:

```python
# Example: Get patients
@router.get("/patients")
async def list_patients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # ✅ Automatically filters by practice_id
    result = await db.execute(
        select(Patient).where(
            Patient.practice_id == current_user.practice_id
        )
    )
    return result.scalars().all()
```

---

## 🔍 AUDIT CHECKLIST

### Phase 1: Code Review (2 hours)

**Verify every endpoint filters by `practice_id`**:

```bash
# Search for queries WITHOUT practice_id filter
cd coredent-api
grep -r "select(" app/api/v1/endpoints/ | grep -v "practice_id"
```

**Check these critical endpoints**:

- [ ] `/api/v1/patients` - List patients
- [ ] `/api/v1/patients/{id}` - Get patient details
- [ ] `/api/v1/appointments` - List appointments
- [ ] `/api/v1/appointments/{id}` - Get appointment
- [ ] `/api/v1/billing/invoices` - List invoices
- [ ] `/api/v1/documents` - List documents
- [ ] `/api/v1/imaging` - List images
- [ ] `/api/v1/insurance/claims` - List claims
- [ ] `/api/v1/reports` - Generate reports

**Red Flags to Look For**:

```python
# ❌ BAD: No practice_id filter
select(Patient).where(Patient.email == email)

# ✅ GOOD: Includes practice_id filter
select(Patient).where(
    Patient.email == email,
    Patient.practice_id == current_user.practice_id
)
```

---

### Phase 2: Automated Testing (1 hour)

Create `tests/test_multi_tenant_isolation.py`:

```python
"""
Multi-Tenant Data Isolation Tests
Ensures Practice A cannot access Practice B's data
"""

import pytest
from httpx import AsyncClient
from app.models.user import User
from app.models.practice import Practice
from app.models.patient import Patient

@pytest.mark.asyncio
async def test_patient_isolation(client: AsyncClient, db):
    """Test that Practice A cannot access Practice B's patients"""
    
    # Create Practice A
    practice_a = Practice(name="Practice A")
    db.add(practice_a)
    
    # Create Practice B
    practice_b = Practice(name="Practice B")
    db.add(practice_b)
    
    # Create patient in Practice A
    patient_a = Patient(
        practice_id=practice_a.id,
        first_name="Alice",
        last_name="Anderson"
    )
    db.add(patient_a)
    
    # Create patient in Practice B
    patient_b = Patient(
        practice_id=practice_b.id,
        first_name="Bob",
        last_name="Brown"
    )
    db.add(patient_b)
    
    await db.commit()
    
    # Login as Practice A user
    token_a = create_access_token({
        "sub": str(user_a.id),
        "practice_id": str(practice_a.id)
    })
    
    # Try to access Practice B's patient (should fail)
    response = await client.get(
        f"/api/v1/patients/{patient_b.id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    
    # ✅ Should return 404 (not found) or 403 (forbidden)
    assert response.status_code in [403, 404]
    
    # ✅ Should NOT return patient data
    assert "Bob" not in response.text

@pytest.mark.asyncio
async def test_appointment_isolation(client: AsyncClient, db):
    """Test that Practice A cannot access Practice B's appointments"""
    # Similar test for appointments
    pass

@pytest.mark.asyncio
async def test_invoice_isolation(client: AsyncClient, db):
    """Test that Practice A cannot access Practice B's invoices"""
    # Similar test for invoices
    pass

@pytest.mark.asyncio
async def test_document_isolation(client: AsyncClient, db):
    """Test that Practice A cannot access Practice B's documents"""
    # Similar test for documents
    pass

@pytest.mark.asyncio
async def test_report_isolation(client: AsyncClient, db):
    """Test that Practice A's reports only show their data"""
    # Create data for both practices
    # Generate report for Practice A
    # Verify it only contains Practice A data
    pass
```

**Run tests**:
```bash
cd coredent-api
pytest tests/test_multi_tenant_isolation.py -v
```

---

### Phase 3: Manual Penetration Testing (1 hour)

**Setup**:
1. Create 2 test practices in Railway database
2. Create test users for each practice
3. Create test data (patients, appointments) for each

**Test Scenarios**:

#### Test 1: Direct ID Access
```bash
# Login as Practice A
TOKEN_A="<practice_a_token>"

# Get Practice B's patient ID from database
PATIENT_B_ID="<practice_b_patient_id>"

# Try to access Practice B's patient
curl -X GET "https://your-api.railway.app/api/v1/patients/$PATIENT_B_ID" \
  -H "Authorization: Bearer $TOKEN_A"

# ✅ Expected: 404 Not Found or 403 Forbidden
# ❌ Failure: Returns patient data
```

#### Test 2: List Endpoint Filtering
```bash
# Login as Practice A
TOKEN_A="<practice_a_token>"

# List all patients
curl -X GET "https://your-api.railway.app/api/v1/patients" \
  -H "Authorization: Bearer $TOKEN_A"

# ✅ Expected: Only Practice A's patients
# ❌ Failure: Shows patients from other practices
```

#### Test 3: Search Endpoint Filtering
```bash
# Login as Practice A
TOKEN_A="<practice_a_token>"

# Search for Practice B's patient by name
curl -X GET "https://your-api.railway.app/api/v1/patients?search=BobBrown" \
  -H "Authorization: Bearer $TOKEN_A"

# ✅ Expected: No results (patient belongs to Practice B)
# ❌ Failure: Returns Practice B's patient
```

#### Test 4: Report Generation
```bash
# Login as Practice A
TOKEN_A="<practice_a_token>"

# Generate revenue report
curl -X GET "https://your-api.railway.app/api/v1/reports/revenue?start_date=2026-01-01&end_date=2026-12-31" \
  -H "Authorization: Bearer $TOKEN_A"

# ✅ Expected: Only Practice A's revenue
# ❌ Failure: Includes revenue from other practices
```

#### Test 5: Token Manipulation
```bash
# Get Practice A token
TOKEN_A="<practice_a_token>"

# Decode token (use jwt.io)
# Try to modify practice_id to Practice B's ID
# Re-encode token

# Try to use modified token
curl -X GET "https://your-api.railway.app/api/v1/patients" \
  -H "Authorization: Bearer $MODIFIED_TOKEN"

# ✅ Expected: 401 Unauthorized (signature invalid)
# ❌ Failure: Returns Practice B's data
```

---

### Phase 4: Database Constraints Verification (30 minutes)

**Check foreign key constraints**:

```sql
-- Connect to Railway database
-- Check that all tables have practice_id foreign key

SELECT 
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND kcu.column_name = 'practice_id';
```

**Expected output**: All major tables should have `practice_id` foreign key

---

## 🚨 Common Vulnerabilities to Check

### 1. Missing practice_id Filter

```python
# ❌ VULNERABLE
@router.get("/patients/{patient_id}")
async def get_patient(patient_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    return result.scalar_one_or_none()

# ✅ SECURE
@router.get("/patients/{patient_id}")
async def get_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == current_user.practice_id  # ✅ Isolation
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
```

### 2. Aggregate Queries Without Filtering

```python
# ❌ VULNERABLE: Counts ALL patients across ALL practices
@router.get("/stats/patient-count")
async def get_patient_count(db: AsyncSession):
    result = await db.execute(select(func.count(Patient.id)))
    return {"count": result.scalar()}

# ✅ SECURE: Only counts current practice's patients
@router.get("/stats/patient-count")
async def get_patient_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(func.count(Patient.id)).where(
            Patient.practice_id == current_user.practice_id
        )
    )
    return {"count": result.scalar()}
```

### 3. JOIN Queries Without Filtering

```python
# ❌ VULNERABLE: Could leak data via JOIN
@router.get("/appointments/{appointment_id}/patient")
async def get_appointment_patient(appointment_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(Patient)
        .join(Appointment)
        .where(Appointment.id == appointment_id)
    )
    return result.scalar_one_or_none()

# ✅ SECURE: Filter both tables
@router.get("/appointments/{appointment_id}/patient")
async def get_appointment_patient(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Patient)
        .join(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.practice_id == current_user.practice_id,  # ✅
            Patient.practice_id == current_user.practice_id  # ✅
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404)
    return patient
```

---

## 📊 Audit Report Template

After completing audit, create report:

```markdown
# Multi-Tenant Isolation Audit Report

**Date**: [Date]
**Auditor**: [Name]
**Status**: ✅ PASS / ❌ FAIL

## Summary
- Total endpoints audited: [X]
- Vulnerabilities found: [X]
- Critical issues: [X]
- Medium issues: [X]
- Low issues: [X]

## Findings

### Critical Issues
1. [Endpoint] - [Description] - [Risk]

### Medium Issues
1. [Endpoint] - [Description] - [Risk]

### Recommendations
1. [Action item]
2. [Action item]

## Test Results
- Code review: ✅ PASS / ❌ FAIL
- Automated tests: ✅ PASS / ❌ FAIL
- Penetration tests: ✅ PASS / ❌ FAIL
- Database constraints: ✅ PASS / ❌ FAIL

## Sign-off
- [ ] All critical issues resolved
- [ ] All tests passing
- [ ] Ready for production

**Approved by**: [Name]
**Date**: [Date]
```

---

## ✅ Quick Audit Script

Create `scripts/audit_multi_tenant.sh`:

```bash
#!/bin/bash
# Quick multi-tenant isolation audit

echo "=== Multi-Tenant Isolation Audit ==="
echo ""

echo "1. Checking for queries without practice_id filter..."
cd coredent-api
grep -r "select(" app/api/v1/endpoints/ | grep -v "practice_id" | grep -v "# OK:" || echo "✅ All queries filtered"

echo ""
echo "2. Running automated tests..."
pytest tests/test_multi_tenant_isolation.py -v

echo ""
echo "3. Checking database constraints..."
railway run psql $DATABASE_URL -c "
SELECT table_name 
FROM information_schema.columns 
WHERE column_name = 'practice_id' 
ORDER BY table_name;
"

echo ""
echo "=== Audit Complete ==="
```

---

## 🎯 Action Items

### Immediate (Before Production):
- [ ] Run code review audit (2 hours)
- [ ] Create automated tests (1 hour)
- [ ] Run manual penetration tests (1 hour)
- [ ] Verify database constraints (30 min)
- [ ] Document findings
- [ ] Fix any vulnerabilities found

### Ongoing (Monthly):
- [ ] Re-run automated tests
- [ ] Review new endpoints for isolation
- [ ] Update tests for new features

---

## 📞 Need Help?

If you find vulnerabilities or need assistance:
1. **Stop deployment** immediately
2. Document the issue
3. Fix the vulnerability
4. Re-test before deploying

---

**Status**: ⚠️ Audit needed before production  
**Estimated Time**: 4-5 hours  
**Priority**: **HIGH** (HIPAA compliance requirement)
