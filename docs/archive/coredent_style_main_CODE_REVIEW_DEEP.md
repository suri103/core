# CoreDent PMS - Deep Code Review

**Date:** 2026-05-11
**Scope:** Full frontend codebase review (React + TypeScript + Vite)
**Test Result:** 339/339 tests passing (43/43 files)

---

## Executive Summary

The project is a dental practice management system with a solid component architecture using modern React patterns. However, several **critical security concerns**, **type safety issues**, and **architectural anti-patterns** need immediate attention before production deployment.

**Risk Level: HIGH** - Several security and data integrity issues present.

---

## 1. Security Issues

### 1.1 CRITICAL: PHI Stored in localStorage (`src/lib/cache.ts`)

```
Line 308: export const localCache = { set<T>(key, data, ttl) { localStorage.setItem(...) } }
```

- **Issue:** The `localCache` utility stores data in `localStorage`, which is vulnerable to XSS extraction. The file even contains a `SECURITY WARNING` comment acknowledging this, yet the code is still used throughout the app.
- **HIPAA Impact:** Protected Health Information (PHI) cached in localStorage can be stolen by any injected script.
- **Fix:** Remove `localCache` entirely or restrict it to non-PHI data only. Use `MemoryCache` for all PHI.

### 1.2 HIGH: CSRF Token Stored in sessionStorage (`src/lib/csrf.ts`)

```
Line 20: sessionStorage.setItem(CSRF_TOKEN_KEY, token);
```

- **Issue:** CSRF tokens are stored in `sessionStorage`, which is accessible to JavaScript (unlike `httpOnly` cookies). An XSS vulnerability would expose both the auth token (in memory) AND the CSRF token (in sessionStorage), making the CSRF protection useless.
- **Fix:** CSRF tokens should be `httpOnly` cookies set by the backend, not client-side storage.

### 1.3 HIGH: Dev Auth Bypass Has Race Condition (`src/contexts/AuthContext.tsx`)

```
Line 21: if (import.meta.env.MODE === 'production' && import.meta.env.VITE_DEV_BYPASS_AUTH === 'true') { throw new Error(...) }
```

- **Issue:** The production safety check runs at module load time, not at runtime. A malicious build could strip this check. The env var is also baked into the bundle at build time, so inspecting the bundle would reveal the bypass mechanism.
- **Fix:** Remove dev bypass code entirely from production builds using `define` in Vite config, rather than runtime checks.

### 1.4 MEDIUM: `window.confirm` Used for Destructive Actions

```
src/pages/Appointments.tsx:250    if (window.confirm('Are you sure...'))
src/pages/Appointments_Refactored.tsx:178    if (window.confirm('Are you sure...'))
src/components/insurance/InsuranceList.tsx:47    if (!window.confirm('Are you sure...'))
```

- **Issue:** `window.confirm` blocks the main thread and provides poor UX. It's also easily bypassed in automated testing and can be confusing to users.
- **Fix:** Use a proper confirmation dialog component (e.g., Radix AlertDialog) with async confirmation.

### 1.5 MEDIUM: Phone Numbers Exposed via `tel:` Links

```
src/pages/patients/PatientList.tsx:345
window.location.href = `tel:${patient.phone}`
```

- **Issue:** Patient phone numbers are exposed in the DOM as clickable links. While minor, this could be scraped by malicious extensions.
- **Fix:** Mask phone numbers in the UI and only reveal on interaction.

### 1.6 LOW: `console.log` in Production Code

```
src/pages/Reports.tsx:85    console.log('[Reports] Loading metrics...')
src/hooks/useApiRequest.ts:33    console.log('[useApiRequest] Response:', ...)
src/hooks/useApiRequest.ts:48    console.error('[useApiRequest] Error:', ...)
```

- **Issue:** Debug logging left in production can leak internal state and API response structures.
- **Fix:** Replace all `console.*` with the `logger` utility which respects environment.

---

## 2. Type Safety Issues

### 2.1 CRITICAL: Extensive Use of `any` Type

**Count:** 40+ instances of explicit `any` across the codebase.

**Worst offenders:**
- `src/lib/i18n.ts` - Translation system uses `Record<string, any>`
- `src/hooks/useApiRequest.ts` - API function typed as `(...args: any[]) => Promise<any>`
- `src/components/appointments/*.tsx` - Stub components use `any[]` for props
- `src/lib/errorRecovery.ts` - Debounce/throttle use `any[]`

**Impact:** TypeScript compiler cannot catch refactoring errors, null dereferences, or API contract violations.

**Fix:** Replace all `any` with proper interfaces. Use `unknown` for external data and narrow with type guards.

### 2.2 HIGH: Missing Return Types on Exported Functions

```
src/hooks/useAppointmentStats.ts
export function useAppointmentStats(_appointments?: any[]) {
  return { total: 0, confirmed: 0, pending: 0, cancelled: 0 };
}
```

- **Issue:** No explicit return type. Consumers may rely on properties that don't exist.
- **Fix:** Add return type annotations to all exported functions.

### 2.3 MEDIUM: `as EventListener` Type Assertions

```
src/lib/i18n.ts:420
window.addEventListener('localechange', handleLocaleChange as EventListener);
```

- **Issue:** Forced type casting hides actual type mismatches.
- **Fix:** Define proper event types or use `CustomEvent` generic.

---

## 3. Architecture & Code Quality

### 3.1 HIGH: Circular Import Risk in Services

`src/services/api.ts` imports from `src/lib/logger.ts`, which may import from `src/services/api.ts` indirectly. The logger file also calls `sendToMonitoring` which could create circular dependencies.

### 3.2 HIGH: Stub Components in Production Source

The following files are test stubs that should NOT be in `src/components/`:

```
src/components/appointments/AppointmentListView.tsx
src/components/appointments/AppointmentStatCard.tsx
src/components/appointments/AppointmentTimelineView.tsx
src/components/appointments/AppointmentTypesView.tsx
src/components/appointments/AppointmentForm.tsx (likely stub)
```

- **Issue:** These are minimal mock components created for tests. They will render in production if the real components are missing.
- **Fix:** Either implement real components or move stubs to `__mocks__/` directory.

### 3.3 HIGH: `useApi.ts` is a Stub Hook

```
src/hooks/useApi.ts
export function useApi<T = unknown>(_endpoint: string): UseApiResult<T> {
  const [loading, setLoading] = useState(true);
  // ... never fetches actual data
  return { loading, data: null, error: null, refetch };
}
```

- **Issue:** This hook accepts an endpoint but never makes a request. It's only used in tests.
- **Fix:** Implement actual data fetching or remove from production code.

### 3.4 MEDIUM: `useEffect` Missing Dependencies

```
src/pages/Reports.tsx:84
useEffect(() => {
  console.log('[Reports] Loading metrics for date range:', dateRange);
  loadMetrics(dateRange);
}, [dateRange, loadMetrics]);
```

- The dependency array looks correct, but `loadMetrics` may not be memoized properly via `useCallback`, causing unnecessary re-fetches.

### 3.5 MEDIUM: Global State in Module Scope

```
src/hooks/use-toast.ts:22
let count = 0;
```

- **Issue:** Module-level mutable state can cause issues with SSR, multiple React roots, or test isolation.
- **Fix:** Use `useRef` or React state management instead.

### 3.6 MEDIUM: `window` Access Without Guards

```
src/services/api.ts:111
if (!window.location.pathname.startsWith('/login')) {
  window.location.href = '/login';
}
```

- **Issue:** Will crash during SSR or testing environments without `window`.
- **Fix:** Add `typeof window !== 'undefined'` guards.

---

## 4. Performance Issues

### 4.1 MEDIUM: No Memoization in List Components

The `AppointmentListView` stub and likely the real list components don't use `React.memo`, causing unnecessary re-renders when parent state changes.

### 4.2 MEDIUM: Inline Object/Function Props

Many components likely create inline objects and functions in render, causing child components to re-render unnecessarily. The pattern is common in Radix UI wrapper components.

### 4.3 LOW: Bundle Size Concerns

The `package.json` includes many heavy dependencies:
- `@radix-ui/react-*` - 30+ Radix packages (tree-shaking helps, but still large)
- `recharts` - Charting library (large)
- `framer-motion` - Animation library (heavy)
- `vaul` - Drawer component (duplicates Radix Dialog functionality)

**Recommendation:** Audit unused Radix packages and remove `vaul` if Radix Dialog covers the use case.

---

## 5. Testing Issues

### 5.1 HIGH: Integration Tests Mock All Data

`Appointments.integration.test.tsx` mocks ALL hooks including `useAppointments`, `useAppointmentTypes`, etc. This means it's testing component rendering logic, not integration. True integration tests should use MSW (already in devDependencies) to intercept API calls.

### 5.2 MEDIUM: `require()` Used in Tests

While mostly fixed, some tests may still use CommonJS `require()` in ESM environments, causing brittle mocking.

### 5.3 MEDIUM: Missing Error Boundary Tests

No tests found for the error boundary component (`components/error-boundary.tsx`).

---

## 6. Accessibility Issues

### 6.1 MEDIUM: Missing `aria-label` on Icon-Only Buttons

Many icon buttons in the UI likely lack `aria-label` attributes. The `Button` component supports `asChild` but doesn't enforce accessibility props.

### 6.2 MEDIUM: Dialog Focus Management

The `Dialog` component from Radix should handle focus trapping, but custom dialogs (like the appointment form) need verification.

### 6.3 LOW: Color Contrast

The `text-yellow-500` class used for pending appointments may not meet WCAG AA contrast ratios against light backgrounds.

---

## 7. Data Integrity & Error Handling

### 7.1 HIGH: Silent Failures in Auth Context

```
src/contexts/AuthContext.tsx:75
catch {
  // Session check failed - treat as logged out
  clearCsrfToken();
  authApi.setToken(null);
}
```

- **Issue:** The catch block silently swallows errors. If the API is down, users get logged out without explanation.
- **Fix:** Distinguish between network errors (show retry) and auth failures (redirect to login).

### 7.2 HIGH: No Retry Logic for Critical Mutations

The `useApiRequest` hook and mutation hooks don't implement retry logic for network failures. A temporary network blip could lose appointment creation data.

### 7.3 MEDIUM: Form State Not Reset on Error

In `Login.tsx`, if login fails, `setIsSubmitting(false)` is called but form fields are not cleared. This is correct for UX, but password should be cleared on repeated failures (brute force mitigation).

---

## 8. Best Practices Violations

### 8.1 File Organization

- **Issue:** Stubs mixed with real components in `src/components/`
- **Issue:** Hooks scattered between `src/hooks/` and `src/lib/`
- **Issue:** Service files in `src/services/` and API types in `src/types/` - good separation

### 8.2 Naming Conventions

- **Issue:** `use-toast.ts` uses kebab-case while other hooks use camelCase
- **Issue:** Some files use `.tsx` extension when they contain no JSX

### 8.3 Import Order

Some files don't follow a consistent import ordering (React, external libs, internal absolute, internal relative).

---

## 9. Recommendations Summary

### Immediate (Before Production)

1. **Remove or restrict `localCache`** - Do not store PHI in localStorage
2. **Move CSRF token to httpOnly cookie** - Backend must set this
3. **Remove dev auth bypass from production builds** - Use build-time removal, not runtime checks
4. **Implement real appointment components** - Current stubs will break production UX
5. **Add explicit return types** to all exported functions
6. **Remove all `console.*` calls** from production code

### Short Term (Next Sprint)

7. Replace `any` types with proper interfaces (start with API layer)
8. Implement proper error handling with user-friendly messages
9. Add retry logic for network failures
10. Write true integration tests using MSW instead of mocked hooks
11. Add accessibility labels to icon-only buttons
12. Add error boundary tests

### Long Term (Technical Debt)

13. Audit bundle size and remove unused dependencies
14. Implement proper loading skeletons for all async data
15. Add React Query devtools in development
16. Consider migrating from `sessionStorage` CSRF to Double Submit Cookie pattern
17. Add Content Security Policy (CSP) headers
18. Implement proper audit logging for PHI access

---

## 10. Positive Findings

- **TypeScript strict mode** appears to be enabled (no implicit any complaints in tests)
- **React Query** is used for server state management (good pattern)
- **Zod** is used for form validation
- **Radix UI** primitives provide solid accessibility foundation
- **Vite** build tool is modern and fast
- **Test coverage** is comprehensive (339 tests passing)
- **Security awareness** - Comments show HIPAA compliance was considered
- **Token storage** - In-memory only (correct for auth tokens)
- **CSRF protection** - Present in API client
- **Timeout handling** - API requests have 30s timeout with AbortController

---

*Review generated by AI code analysis. Manual review of complex logic paths recommended.*
