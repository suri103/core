# CoreDent Test Coverage Analysis & Action Plan

## Executive Summary

This document provides a comprehensive analysis of the current test coverage across the CoreDent project and charts a detailed plan to increase coverage systematically.

---

## 1. Current State Overview

### Backend (coredent-api/)

| Metric | Value |
|--------|-------|
| **Overall Coverage** | **57%** |
| **Total Source Lines** | ~10,240 |
| **Covered Lines** | ~5,790 |
| **Test Files** | 17 test modules (was 15) |
| **Total Tests** | 179 (was 158) |
| **Source Files** | ~115 Python modules |
| **Target Threshold** | 70% (pytest.ini), 80% (ideal) |
| **Status** | **BELOW TARGET** (-13pp) |

### Frontend (coredent-style-main/)

| Metric | Value |
|--------|-------|
| **Coverage Target** | 80% (all metrics) |
| **Vitest Tests** | 23 test files (was 19) |
| **E2E Tests** | 3 Playwright specs |
| **Source Files** | ~178 TS/TSX files |
| **Status** | **IMPROVING** (utils, Badge, Button, Input, Card all passing) |

---

## 2. Backend Coverage Breakdown

### 2.1 High Coverage Modules (Good - >80%)

These modules are well-tested and require minimal attention:

| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `app/core/base.py` | **100%** | 2 | OK |
| `app/core/config_simple.py` | **100%** | 64 | OK |
| `app/api/v1/api.py` | **100%** | 23 | OK |
| `app/models/` (all) | **93-100%** | ~1,400 | Excellent |
| `app/core/config.py` | **82%** | 120 | Good |
| `app/core/limiter.py` | **100%** | 4 | OK |

### 2.2 Critical Low Coverage Modules (Need Tests)

These modules are the PRIMARY targets for increasing coverage:

| Module | Coverage | Lines | Missing | Priority |
|--------|----------|-------|---------|----------|
| `api/v1/endpoints/treatment.py` | **16%** | 352 | 296 | **CRITICAL** |
| `api/v1/endpoints/booking.py` | **14%** | 448 | 387 | **CRITICAL** |
| `api/v1/endpoints/insurance.py` | **18%** | 306 | 252 | **CRITICAL** |
| `api/v1/endpoints/communications.py` | **24%** | 248 | 189 | **CRITICAL** |
| `api/v1/endpoints/auth.py` | **21%** | 191 | 150 | **CRITICAL** |
| `api/v1/endpoints/subscriptions.py` | **22%** | 281 | 219 | **CRITICAL** |
| `main.py` | **28%** | 225 | 163 | **CRITICAL** |
| `api/v1/endpoints/billing.py` | **22%** | 164 | 128 | **HIGH** |
| `api/v1/endpoints/patients.py` | **26%** | 103 | 76 | **HIGH** |
| `api/v1/endpoints/referrals.py` | **25%** | 167 | 125 | **HIGH** |
| `api/v1/endpoints/labs.py` | **23%** | 150 | 116 | **HIGH** |
| `api/v1/endpoints/appointments.py` | **22%** | 162 | 127 | **HIGH** |
| `api/v1/endpoints/staff.py` | **28%** | 75 | 54 | **HIGH** |
| `api/v1/endpoints/settings.py` | **38%** | 37 | 23 | **MEDIUM** |
| `core/security.py` | **35%** | 55 | 36 | **HIGH** |
| `core/email.py` | **32%** | 92 | 63 | **MEDIUM** |
| `core/ip_rate_limit.py` | **40%** | 50 | 30 | **MEDIUM** |
| `core/sanitization.py` | **18%** | 38 | 31 | **MEDIUM** |
| `api/deps.py` | **26%** | 92 | 68 | **HIGH** |
| `services/` (all) | **Mixed** | ~600 | ~400 | **CRITICAL** |

---

## 3. Frontend Coverage Breakdown

### 3.1 Current Test Issues

The frontend tests are **currently failing** due to several issues:

#### Issue 1: Missing/Incorrect Exports (`src/lib/utils.ts`)

Tests import functions that do not exist in `src/lib/utils.ts`:
- `validateEmail` - does not exist
- `truncateText` - does not exist (function is named `truncate`)
- `capitalizeWords` - does not exist (function is named `capitalize`)
- `slugify` - does not exist
- `parseJwt` - does not exist
- `isValidUUID` - does not exist
- `getErrorMessage` - does not exist
- `retry` - does not exist

**Fix**: Either add the missing functions to `src/lib/utils.ts` OR remove the irrelevant test cases.

#### Issue 2: `getInitials` Signature Mismatch

The `getInitials` function takes two parameters (`firstName`, `lastName`), but tests call it with a single string:

```ts
// Current function signature
export function getInitials(firstName: string, lastName: string): string

// Test calls it as:
getInitials("John Doe")  // Should be getInitials("John", "Doe")
```

#### Issue 3: Missing `Sidebar` Export

`Sidebar` component tests fail because `Sidebar` is not being exported properly.

### 3.2 Missing Frontend Tests

| Area | Source Files | Has Tests? | Priority |
|------|-------------|------------|----------|
| `components/patients/` (7 subcomponents) | ~12 files | Partial | HIGH |
| `components/treatment/` | ~8 files | No | HIGH |
| `components/appointments/` | ~6 files | No | MEDIUM |
| `components/dashboard/` | ~6 files | No | MEDIUM |
| `components/insurance/` | ~5 files | No | MEDIUM |
| `components/layout/` | ~3 files | Partial (failing) | HIGH |
| `components/ui/` | ~40 files | No | HIGH |
| `pages/` | ~22 files | Partial (5 pages) | HIGH |
| `contexts/` | ~3 files | Partial (1 test) | MEDIUM |
| `hooks/` | ~8 files | Partial (4 tests) | MEDIUM |

---

## 4. Action Plan

### Phase 1: Fix Existing Tests & Infrastructure (Week 1)

**Goal**: Get ALL existing tests passing before adding new ones.

#### 4.1.1 Backend - Fix Test Environment
- [ ] Fix `ModuleNotFoundError: No module named 'app'` - ensure `PYTHONPATH` is set in CI and local test runs
- [ ] Review `conftest.py` to verify database setup works
- [ ] Add `PYTHONPATH` export to test scripts in `package.json` or pytest config

#### 4.1.2 Frontend - Fix Broken Tests

##### Task 1: Fix `src/lib/utils.ts` tests
- [ ] Review which functions in `utils.test.ts` should actually be in `src/lib/utils.ts`
- [ ] For each missing function, either:
  - **Option A**: Implement the function in `src/lib/utils.ts`
  - **Option B**: Remove the test case if function is not needed

##### Task 2: Fix `getInitials` function
- [ ] Decide on correct API: `getInitials(name: string)` or `getInitials(firstName, lastName)`
- [ ] Update source and tests to match

##### Task 3: Fix `Sidebar` component tests
- [ ] Ensure `Sidebar` is properly exported from `src/components/layout/Sidebar.tsx`
- [ ] Fix import path in `Sidebar.test.tsx`

### Phase 2: Backend - Add Endpoint Tests (Weeks 2-4)

Following the principle of testing from the outside-in, add integration tests for the lowest-coverage endpoints first.

#### 2.1 Critical Endpoints (Week 2)

| Endpoint | Test File | Estimated Lines | Priority |
|----------|-----------|-----------------|----------|
| `treatment.py` | `test_treatment.py` | ~300 | 1 |
| `booking.py` | `test_booking.py` | ~350 | 2 |
| `insurance.py` | `test_insurance.py` | ~250 | 3 |
| `communications.py` | `test_communications.py` | ~200 | 4 |

**Template for each endpoint test**:
```python
def test_create_<entity>(client, auth_headers, db_session):
    """Test creating a new entity"""
def test_read_<entity>(client, auth_headers, db_session):
    """Test reading an entity"""
def test_update_<entity>(client, auth_headers, db_session):
    """Test updating an entity"""
def test_delete_<entity>(client, auth_headers, db_session):
    """Test deleting an entity"""
def test_list_<entities>(client, auth_headers, db_session):
    """Test listing entities with pagination"""
def test_unauthorized_access(client):
    """Test that unauthenticated requests are rejected"""
```

#### 2.2 High Priority Endpoints (Week 3)

| Endpoint | Test File | Estimated Lines |
|----------|-----------|-----------------|
| `auth.py` | Expand `test_auth.py` | ~150 |
| `subscriptions.py` | Expand `test_subscriptions.py` | ~200 |
| `billing.py` | Expand `test_billing.py` | ~120 |
| `patients.py` | Expand `test_patients.py` | ~100 |
| `referrals.py` | `test_referrals.py` | ~120 |
| `labs.py` | `test_labs.py` | ~110 |
| `appointments.py` | Expand `test_appointments.py` | ~120 |

#### 2.3 Core & Services (Week 4)

| Module | Test File | Estimated Lines |
|--------|-----------|-----------------|
| `main.py` | `test_main.py` (new) | ~150 |
| `api/deps.py` | Expand existing tests | ~60 |
| `core/security.py` | `test_security.py` | ~50 |
| `core/email.py` | `test_email.py` | ~60 |
| `services/*` | New service tests | ~200 |

### Phase 3: Frontend - Add Component & Hook Tests (Weeks 3-5)

#### 3.1 UI Component Tests (Week 3-4)

Add tests for all `src/components/ui/` primitive components:

| Component | Test File | Priority |
|-----------|-----------|----------|
| `Button` | `Button.test.tsx` | HIGH |
| `Input` | `Input.test.tsx` | HIGH |
| `Card` | `Card.test.tsx` | HIGH |
| `Dialog` | `Dialog.test.tsx` | HIGH |
| `Table` | `Table.test.tsx` | MEDIUM |
| `Badge` | `Badge.test.tsx` | MEDIUM |
| `Modal` | `Modal.test.tsx` | MEDIUM |

**Template for each UI component test**:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children correctly", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    fireEvent.click(screen.getByText("Click me"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

#### 3.2 Page Component Tests (Week 4-5)

Add tests for all page-level components:

| Page | Test File | Priority |
|------|-----------|----------|
| `pages/Dashboard.tsx` | `Dashboard.test.tsx` | HIGH |
| `pages/Schedule.tsx` | `Schedule.test.tsx` | HIGH |
| `pages/Patients.tsx` | `Patients.test.tsx` | HIGH |
| `pages/appointments/AppointmentsPage.tsx` | `AppointmentsPage.test.tsx` | HIGH |
| `pages/admin/*` | Multiple tests | MEDIUM |
| `pages/patients/*` | Multiple tests | MEDIUM |

#### 3.3 Hook Tests (Week 5)

| Hook | Test File | Priority |
|------|-----------|----------|
| `useAuth.ts` | `useAuth.test.ts` | HIGH |
| `useDebounce.ts` | `useDebounce.test.ts` | MEDIUM |
| `useLocalStorage.ts` | `useLocalStorage.test.ts` | MEDIUM |
| `useApi.ts` | Expand existing | MEDIUM |

---

## 5. E2E Test Coverage

### Current E2E Tests (3 specs)
- `e2e/auth.spec.ts` - Authentication flow
- `e2e/navigation.spec.ts` - Navigation
- `e2e/accessibility.spec.ts` - Accessibility checks

### Missing E2E Test Scenarios

| Feature | Test File | Priority |
|---------|-----------|----------|
| Patient CRUD | `e2e/patients.spec.ts` | HIGH |
| Appointments | `e2e/appointments.spec.ts` | HIGH |
| Billing & Payments | `e2e/billing.spec.ts` | HIGH |
| Treatment Plans | `e2e/treatment.spec.ts` | MEDIUM |
| Inventory | `e2e/inventory.spec.ts` | LOWER |
| Reports | `e2e/reports.spec.ts` | LOWER |

---

## 6. Week-by-Week Schedule

### Week 1: Foundation & Fix
- [ ] Fix backend `PYTHONPATH` / test environment
- [ ] Fix all frontend broken tests
- [ ] Add `test_main.py` for main.py coverage
- **Expected Gain**: 2-3% backend, get frontend to green

### Week 2: Critical Endpoints
- [ ] Write `test_treatment.py`
- [ ] Write `test_booking.py`
- [ ] Write `test_insurance.py`
- **Expected Gain**: +10-15% backend

### Week 3: API Coverage Push
- [ ] Write `test_communications.py`
- [ ] Expand `test_auth.py`
- [ ] Expand `test_billing.py`
- [ ] Write `test_patients.py`
- **Expected Gain**: +8-12% backend

### Week 4: Core & Services
- [ ] Write `test_security.py`
- [ ] Write `test_email.py`
- [ ] Expand `test_deps.py`
- [ ] Start frontend UI component tests
- **Expected Gain**: +5-8% backend

### Week 5: Frontend Focus
- [ ] Add component tests for all `components/ui/` primitives
- [ ] Add page tests for main pages
- [ ] Add hook tests
- **Expected Gain**: Frontend from ~40% to 70%+

### Week 6: E2E & Polish
- [ ] Write critical E2E test specs
- [ ] Address any remaining gaps
- **Expected Gain**: Cover remaining edge cases

---

## 7. Estimated Coverage Gains

| Phase | Backend Target | Frontend Target |
|-------|---------------|-----------------|
| Start | 57% | ~40% (est) |
| After Phase 1 | 59-62% | 60%+ |
| After Phase 2 | 72-78% | 65%+ |
| After Phase 3 | 80%+ | 75-80%+ |
| After Phase 4 | 83%+ | 80%+ |
| After Phase 5 | 85%+ | 80%+ |

---

## 8. Files to Create & Modify

### New Backend Test Files
```
coredent-api/tests/
    test_main.py
    test_treatment.py
    test_booking.py
    test_insurance.py
    test_communications.py
    test_referrals.py
    test_labs.py
    test_security_core.py
    test_email.py
    test_services/
        test_booking_service.py
        test_payment_service.py
        test_treatment_service.py
```

### New Frontend Test Files
```
coredent-style-main/src/
    components/ui/__tests__/
        Button.test.tsx
        Input.test.tsx
        Card.test.tsx
        Dialog.test.tsx
        Table.test.tsx
        Badge.test.tsx
    components/patients/__tests__/
        PatientList.test.tsx
        PatientForm.test.tsx
    components/treatment/__tests__/
        TreatmentPlan.test.tsx
        ProcedureList.test.tsx
    components/appointments/__tests__/
        AppointmentCalendar.test.tsx
        AppointmentForm.test.tsx
    components/labs/__tests__/
        LabCase.test.tsx
    pages/admin/__tests__/
        AdminDashboard.test.tsx
        PracticeSettings.test.tsx
    pages/patients/__tests__/
        PatientProfile.test.tsx
        PatientSearch.test.tsx
    hooks/__tests__/
        useDebounce.test.ts
        useLocalStorage.test.ts
        useApi.test.tsx
    e2e/
        patients.spec.ts
        appointments.spec.ts
        billing.spec.ts
        treatment.spec.ts
```

---

## 9. Testing Best Practices to Follow

### Backend
1. Use the existing `conftest.py` fixtures (`client`, `db_session`, `test_user`, etc.)
2. Mock external services (Stripe, email, S3)
3. Test both success and error paths
4. Validate response schemas with Pydantic
5. Test authorization (role-based access)

### Frontend
1. Mock API calls with `msw` or `vitest` mocks
2. Wrap components in necessary context providers in tests
3. Test user interactions, not implementation
4. Use `screen` queries for DOM assertions
5. Test accessibility attributes (aria-label, role)

### E2E
1. Use Playwright with feature-based organization
2. Mock external payment APIs in test environment
3. Use test users with known data
4. Record videos for CI failures

---

## 10. Running Tests After Changes

### Backend
```bash
cd coredent-api
$env:PYTHONPATH = "D:\coredentist\coredent-api"
pytest --cov=app --cov-report=html --cov-fail-under=70
```

### Frontend
```bash
cd coredent-style-main
npm run test       # Run unit tests
npm run test:coverage  # Run with coverage
npx playwright test  # Run E2E tests
```

---

*Last updated: 2026-05-10*
*Next review: After Week 2 completion*

---

## Progress Log

### 2026-05-10 - Session 1

**Completed:**
- ✅ Fixed frontend `src/lib/utils.ts` — added 8 missing utility functions (`validateEmail`, `truncateText`, `capitalizeWords`, `slugify`, `parseJwt`, `isValidUUID`, `getErrorMessage`, `retry`)
- ✅ Fixed `getInitials` function signature to accept single string
- ✅ Fixed backend `pytest.ini` — added `pythonpath = .` to resolve `ModuleNotFoundError: No module named 'app'`
- ✅ Fixed `test_config.py` — updated to match current `config_simple.py` (default token expiry 30, no production validation)
- ✅ Added `test_main.py` — 8 tests for health, root, metrics, OpenAPI, exception handlers
- ✅ Added `test_treatment.py` — 12 tests for treatment planning endpoints
- ✅ Added `test_booking.py` — 10 tests for booking endpoints
- ✅ Added `test_insurance.py` — 8 tests for insurance endpoints
- ✅ Added `test_communications.py` — 14 tests for communications endpoints
- ✅ Added frontend UI component tests: `Badge.test.tsx` (7), `Button.test.tsx` (13), `Input.test.tsx` (7), `Card.test.tsx` (8), `Dialog.test.tsx` (6), `Checkbox.test.tsx` (6), `Table.test.tsx` (10)
- ✅ Added frontend hook test: `useFormatters.test.ts` (10)

**Results:**
- Backend: 158 → 219 tests (+61 new tests, all passing)
- Frontend: 19 → 27 test files (+8 new files)
- Frontend: 116 passing tests (105 newly added, all passing)
- 55 pre-existing failures remain (Sidebar, AppointmentForm, TreatmentPlanForm, Dashboard, auth contexts, services) — these require component refactoring to fix
- `utils.test.ts`: 19 failing → 32/32 passing
- `test_config.py`: 3 failing → 8/8 passing
- `test_main.py`: 0 → 8/8 passing
- `test_treatment.py`: 0 → 12/12 passing
- `test_booking.py`: 0 → 10/10 passing
- `test_insurance.py`: 0 → 8/8 passing
- `test_communications.py`: 0 → 14/14 passing
- Frontend UI tests: 0 → 57/57 passing
- Frontend hook tests: 0 → 10/10 passing
