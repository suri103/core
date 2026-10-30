# Static Security Scan — 2026-08-09

Scope: frontend `coredent-style-main/src` and backend `coredent-api/app`.
Method: targeted static scans (grep/ripgrep-style) + targeted code review of
each finding surface. No external tooling was introduced.

## Findings and disposition

### 1. Storage (localStorage / sessionStorage) — ✅ PASS
- **No tokens** are written to any storage API. `AuthContext` confirms
  "removed for HIPAA compliance"; the refresh token is in memory only and
  `ApiClient` even cleans up the legacy `cd_rt` entry.
- `lib/cache.ts` `localCache.set()` has a **PHI blocklist**:
  `/(patient|appointment|clinical|treatment|billing|insurance|note|chart|report)/i`
  throws before any PHI-keyed write (tested in `cache.test.ts:309-310`).
  `sessionCache`/`MemoryCache` are the sanctioned stores for sensitive data.
- `lib/i18n.ts` persists only the UI locale — not sensitive.

### 2. PHI logging — ✅ PASS (two hardening changes in this pass)
- `app/main.py` error logger redacts PHI **keys** before logging. Found and
  fixed a real bug: `redact_phi` was a **set comprehension** (no colon), so it
  crashed with `TypeError: unhashable type` on nested bodies and, when it
  didn't crash, discarded key/value association — leaking raw attacker
  key/value content into the log. Now a dict comprehension, with
  `_looks_like_phi_key` matching raw, lowercase, and camel→snake forms
  (including `dateOfBirth` → `date_of_birth`).
- `app/services/communications_service.py`: inbound-SMS warning logged the
  full inbound phone number; now redacts (keeps last 4 digits).
- `app/core/email.py` `_send_console` prints From/To/Subject/body, but the
  console sink is gated to non-production and raises in production — accepted.
- `app/core/tasks.py` logs practice/admin email addresses that are already the
  send *destination* of the daily-summary email — accepted (operator context).

### 3. Unsafe HTML — ✅ PASS
- Only three `dangerouslySetInnerHTML` sites:
  - `components/ui/chart.tsx` — static CSS variables generated from a config
    object (no user input).
  - `pages/PublicBooking.tsx` — static CSS string (no interpolation of user
    data).
  - `components/SanitizedContent.tsx` — always routes through `sanitizeHtml` /
    `sanitizePatientNote` (DOMPurify-backed) before injection; text mode never
    uses `dangerouslySetInnerHTML`.
- `lib/sanitize.ts` provides the sanitizers; covered by `sanitize.test.ts`.

### 4. Demo / dev bypass — ✅ PASS
- `AuthContext.tsx` gates `DEV_BYPASS_AUTH` behind `import.meta.env.MODE ===
  'development'` AND `VITE_DEV_BYPASS_AUTH === 'true'`, and **throws** if it
  is ever truthy while `MODE === 'production'`.
- `.env.production.example` sets `VITE_DEV_BYPASS_AUTH=false`;
  `.env.staging.example` also sets it false.

### 5. Raw `fetch` usage — ✅ PASS (documented residue)
- `services/api.ts`: the audited client (CSRF, Bearer, refresh, 401 retry) and
  the token-refresh helper — expected.
- `pages/PatientPortal.tsx`: portal endpoints using the portal session token +
  `credentials` — in scope of the portal contract, audited.
- `pages/PublicBooking.tsx`: fully public endpoints — expected.
- `lib/featureFlags.ts` / `lib/monitoring.ts`: public config / analytics
  beacons — expected.
- **Residue:** `hooks/useApi.ts` performs raw `fetch` with `credentials:
  'include'` but no Bearer token and no refresh/CSRF handling. It is **not
  referenced by any page or component** (only its own test). If it is ever
  wired to authenticated endpoints it will leak 401s and bypass the client;
  recommend deleting the hook or routing it through `apiClient`.

## Verification artifacts
- `npm audit` (after `npm audit fix`): **0 vulnerabilities**.
- `npm run audit:prod`: **passed with no advisories**.
- `pip-audit --strict -r requirements.txt` (after cryptography→50.x and
  removing the unused `fastapi-mail` pin): **No known vulnerabilities found**.
- `cryptography==50.0.0` with encryption/PHI-at-rest/file-security suites:
  **53 passed**.

## Residual, non-code items (unchanged)
Live staging E2E (Playwright specs in `coredent-style-main/e2e`) requires a
running staging deployment with real credentials; container topology requires
a Docker staging smoke test. See `PRODUCTION_STATUS.md`.