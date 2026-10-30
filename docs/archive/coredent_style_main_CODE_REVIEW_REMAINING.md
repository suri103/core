# CoreDent Frontend — Remaining Issues Review

**Review Date:** 2026-05-11
**Reviewer:** Cascade (post-Kimi & Claude Opus review consolidation)
**Test Status:** 43/43 files passing, 340/340 tests passing

---

## Executive Summary

The codebase is in significantly better shape than initial reviews suggested. **All tests pass.** The critical security fixes (PHI in localStorage, auth bypass, token storage, CSRF, CSP) are **done**. However, **one build-breaking issue exists** (`App.tsx` is missing), and several medium-severity type safety, error handling, and architectural issues remain.

---

## 🔴 CRITICAL — Must Fix Before Deploy

### 1. `App.tsx` is Missing — Build Will Fail

**File:** `src/main.tsx:2`
```typescript
import App from "./App.tsx";
```
**Problem:** `App.tsx` does not exist in `src/`. Only `App.css` exists. `main.tsx` imports it unconditionally.
**Impact:** `vite build` / `tsc` will fail with `Cannot find module './App.tsx'`.
**Fix:** Create `src/App.tsx` with the root component (router + providers + ErrorBoundary), or fix the import if the file lives elsewhere.

---

## 🟡 HIGH — Production Risks

### 2. ErrorBoundary Exists But Is NOT Wrapped at App Root

**File:** `src/components/error-boundary.tsx`
**Problem:** The `ErrorBoundary` class component is well-implemented but is **never imported or used** in `main.tsx` or anywhere in the tree. React render crashes will show the default white-screen-of-death.
**Impact:** Users see blank page on unhandled errors; no error logging to Sentry from boundary.
**Fix:** Wrap `<App />` in `main.tsx` with `<ErrorBoundary>`.

### 3. Silent `catch` Blocks Still Swallow Errors (7 files)

| File | Line | Issue |
|------|------|-------|
| `src/pages/ClinicalNotes.tsx` | 90 | `loadPatient` catch swallows error without `logger.error` |
| `src/pages/ClinicalNotes.tsx` | 113 | Search debounce catch swallows error without `logger.error` |
| `src/pages/ClinicalNotes.tsx` | 174 | `handleCreateNote` catch swallows error without `logger.error` |
| `src/contexts/AuthContext.tsx` | 165 | Logout API fail is intentionally silent (acceptable, noted) |
| `src/lib/cache.ts` | multiple | `localStorage`/`sessionStorage` full errors caught silently — **expected** (we clear and retry) |
| `src/lib/apiValidation.ts` | 21 | Zod parse fail logged but returns `null` — **expected pattern** |
| `src/lib/featureFlags.tsx` | ~1 | Silent catch |
| `src/lib/sanitize.ts` | ~1 | Silent catch |
| `src/lib/utils.ts` | ~1 | Silent catch |
| `src/pages/PatientPortal.tsx` | ~1 | Silent catch |
| `src/pages/patients/PatientList.tsx` | ~1 | Silent catch |

**Recommendation:** The 3 in `ClinicalNotes.tsx` are the most dangerous — clinical data operations failing silently. Add `logger.error()` in those catch blocks.

### 4. API Response Casting Without Runtime Validation

**File:** `src/services/api.ts:177`
```typescript
return {
  success: true,
  data: data as T,   // <-- runtime cast, no validation
};
```
**Problem:** The API client casts `await response.json()` directly to `T`. If the backend returns an unexpected shape (extra field, missing field, wrong type), TypeScript is happy but runtime crashes.
**Context:** Zod validation utilities (`validateApiResponse`, `validateApiResponseStrict`) exist in `src/lib/apiValidation.ts` but are **never used** in actual API calls.
**Fix:** Either:
- (Quick) Add a debug-mode warning when `data` shape doesn't match expected keys
- (Proper) Pass Zod schemas into `apiClient.request<T>()` and validate before casting

### 5. `window.location` Usage Without SSR Guard

**Files:**
- `src/components/error-boundary.tsx:42` — `window.location.reload()`
- `src/services/api.ts:121` — `window.location.href = '/login'`
- `src/pages/patients/PatientList.tsx` — `window.location` usage

**Problem:** Hard `window` access without `typeof window !== 'undefined'` guards. Will crash in SSR/test environments that don't mock `window` fully.
**Fix:** Add guard checks or use `useNavigate` from react-router where appropriate.

---

## 🟠 MEDIUM — Type Safety & Code Quality

### 6. `any` Types Remain in Production Code

| File | Count | Locations |
|------|-------|-----------|
| `src/hooks/useSubscriptions.ts` | 6 | `onSuccess` / `onError` callbacks, mutation variables |
| `src/lib/errorRecovery.ts` | 4 | `error as Error`, `onRetry` callback signatures |
| `src/components/reports/charts/BaseChart.tsx` | 3 | `data: any[]`, `formatter?: (v: any) => string` |
| `src/lib/rateLimiter.ts` | 2 | `RequestRecord` type usage |
| `src/pages/PublicBooking.tsx` | 2 | `business_hours: any`, `intake_form_fields: any[]` |
| `src/pages/Subscriptions.tsx` | 2 | Component props |
| `src/lib/i18n.ts` | 1 | `Record<string, Record<string, any>>` — **acceptable** for translation tree |
| `src/pages/PatientPortal.tsx` | 1 | Type assertion |

**Impact:** 21 remaining `any` types. The `BaseChart.tsx` ones are the most impactful (affects all chart rendering). `useSubscriptions.ts` should use proper `MutationOptions` types from React Query.

### 7. `setInterval` Memory Leak in Rate Limiter

**File:** `src/lib/rateLimiter.ts:22`
```typescript
setInterval(() => this.cleanup(), 60000);
```
**Problem:** Interval is started in constructor but **never cleared**. If multiple `RateLimiter` instances are created (e.g., per request), intervals accumulate forever.
**Fix:** Store interval ID and provide a `destroy()` method, or use a singleton pattern.

### 8. Missing `useEffect` Dependency Arrays / `exhaustive-deps`

**Files:** 28 files use `useEffect(() => { ... })` patterns.
**Problem:** The `react-hooks/exhaustive-deps` ESLint rule is **disabled** (per `CODE_REVIEW_DEEP.md`). This means stale closures and infinite re-render risks are not caught automatically.
**Notable risky patterns:**
- `src/pages/ClinicalNotes.tsx:97` — `useEffect` depends on `searchQuery` and `patientId` but calls async functions inside without cleanup race-condition guard
- `src/hooks/useApi.ts` — `useEffect` depends on `fetchData` which depends on `endpoint` — correct, but refetch pattern could race

**Fix:** Re-enable `react-hooks/exhaustive-deps` in ESLint config and fix reported warnings.

### 9. Missing ARIA Labels on Icon-Only Buttons

**Observation:** Only 5 non-test source files contain `aria-label` or `aria-labelledby`. Many UI components use icon-only buttons (e.g., `Trash2`, `Edit`, `Eye`, `X` in tables and dialogs) without `aria-label`.
**Impact:** Screen reader users cannot determine button purpose.
**Fix:** Audit all `<Button>` and `<button>` usages with icon-only children and add `aria-label`.

---

## 🟢 LOW — Polish & Best Practices

### 10. Console Logs in `analytics.ts` and `webVitals.ts`

**Files:**
- `src/lib/analytics.ts` — 1 `console.log`
- `src/lib/webVitals.ts` — 1 `console.log`

These are not the logger utility; they should use `logger.debug()` instead.

### 11. `TODO` / `FIXME` Comments Still in Code

| File | Count |
|------|-------|
| `src/lib/logger.ts` | 5 |
| `src/contexts/AuthContext.tsx` | 3 |
| `src/components/patients/PatientDialog.tsx` | 2 |
| `src/lib/monitoring.ts` | 2 |
| `src/pages/Communications.tsx` | 1 |

Most are documentation/commentary, but some may indicate unfinished work.

### 12. `PublicBooking.tsx` Uses Hardcoded Mock Data

**File:** `src/pages/PublicBooking.tsx:55-71`
The `fetchPublicPage` function returns hardcoded mock data including an Unsplash image URL. This is clearly marked as "For now, returning a mock" but it's in the production source tree.

### 13. `i18n.ts` Reads `localStorage` Directly Without Error Handling

**File:** `src/lib/i18n.ts:24`
```typescript
const savedLocale = localStorage.getItem('locale');
```
`localStorage` access can throw in private browsing / restricted iframes. Wrapped in constructor try/catch would be safer.

---

## ✅ What IS Working Well (Don't Touch)

- **All 340 tests pass** — the test suite is green and well-structured
- **Zod form validation** — `PatientDialog`, `Login`, `AcceptInvitation`, `ResetPassword`, `ForgotPassword` all use Zod schemas properly
- **Security hardening** — No PHI in localStorage, tokens in-memory only, CSRF on state-changing requests, CSP in nginx, auth bypass locked to dev mode
- **Sentry integration** — `logger.ts` now properly sends errors/warnings to Sentry in production
- **Token refresh** — Sends `refresh_token` in body with httpOnly cookie fallback
- **API timeout** — `AbortController` with 30s timeout on all requests
- **Sanitization** — `SanitizedContent` component properly sanitizes user-generated HTML before `dangerouslySetInnerHTML`
- **Rate limiting** — Client-side rate limiter exists (just needs interval cleanup)
- **Feature flags** — Rollout percentage and role-based gating implemented

---

## Recommended Priority Order

1. **Create `src/App.tsx`** — currently missing, build is broken
2. **Wrap `<App />` with `<ErrorBoundary>` in `main.tsx`**
3. **Fix 3 silent catches in `ClinicalNotes.tsx`** — add `logger.error()`
4. **Add SSR guard to `window.location` usages** in `api.ts` and `error-boundary.tsx`
5. **Fix `setInterval` leak in `rateLimiter.ts`**
6. **Replace `any` in `BaseChart.tsx` and `useSubscriptions.ts`**
7. **Re-enable `react-hooks/exhaustive-deps` ESLint rule** and fix warnings
8. **Add `aria-label` to icon-only buttons**
9. **Remove/replace hardcoded mock in `PublicBooking.tsx`**
10. **Wire Zod validation into API client response parsing** (long-term)
