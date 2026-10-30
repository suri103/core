# CoreDent Full-Stack Code Audit — Consolidated Report

**Date:** 2026-08-15
**Scope:** `coredent-api` (FastAPI backend) + `coredent-style-main` (React frontend)
**Method:** Four parallel deep audits — auth/onboarding, payments/billing, patients/appointments, frontend. Every finding below was verified against source with file:line references.

**Totals:** 6 Critical · 16 High · 36 Medium · 25 Low

---

## Executive summary

The core security primitives are solid (JWT handling, bcrypt, refresh-token hashing, tenant scoping on most read paths, Stripe webhook signature verification). The systemic weaknesses are:

1. **Privilege escalation** — an ADMIN can create an OWNER/GROUP_OWNER account (`staff.py` create path), and the frontend invite dialog offers the owner role to any admin. Tenant takeover.
2. **Race conditions** — slot double-booking, booking confirmation, webhook idempotency, patient dedup, and refresh-token rotation are all check-then-insert with no locking.
3. **Money integrity** — billing summary counts failed/refunded payments as collected; invoice edits silently zero tax; refunds never reverse invoices; money is handled in floats.
4. **Naive datetimes** — three separate modules compare naive vs aware datetimes (500s on SQLite/Postgres depending on module, wrong appointment instants, wrong-day UTC bucketing).
5. **Unvalidated state machines** — invoice and appointment statuses accept any transition, corrupting reporting and re-enabling cancelled records.
6. **Frontend data-loss paths** — failed saves show success, patient search sends an ignored param (wrong-chart clinical notes), logout leaves cached PHI for the next user in the same tab.

---

## CRITICAL (6)

### Backend — Payments/Billing

**C1. Billing summary counts FAILED/REFUNDED/PENDING payments as collected.**
`app/api/v1/endpoints/billing.py:485-495` — the `payment_query` in `get_billing_summary` sums all `Payment.amount` with no `Payment.status == COMPLETED` filter. `outstanding_balance = total_revenue - total_collected` (line 515) is understated and can go negative. `reports.py:130-138` filters correctly, so the two summaries disagree.

**C2. Stripe webhook path marks invoices PAID for partial payments; two separate commits lose the money trail.**
`app/services/payment_processing.py:127-143` — `handle_payment_succeeded` calls `mark_invoice_paid` (commits at `payment_service.py:94`) *before* `create_payment_record` (second commit at `payment_service.py:70`). Partial payments are explicitly permitted (`payment_processing.py:63-65`) but any success marks the invoice fully PAID; a crash between the two commits leaves a PAID invoice with no payment record. (Module not currently routed, but it is the exported service API.)

**C3. Webhook idempotency check is not race-safe; `transaction_id` has no unique constraint.**
`app/services/payment_processing.py:118-121` + `app/models/billing.py:115` — check-then-insert with no row lock; two concurrent webhook deliveries both insert, double-counting `Invoice.amount_paid`. Same pattern at Razorpay path lines 334-343.

### Backend — Patients/Appointments

**C4. TOCTOU race on slot booking — double-booking is possible on every write path.**
`app/api/v1/endpoints/appointments.py:328-365` (create), `:413-436` (update), `:592-608` (reschedule); `booking.py:661-704` (confirm). Plain SELECT-then-INSERT with no `with_forupdate`, advisory lock, or DB exclusion constraint (none exists in migrations — yet `billing.py:60-96` uses `pg_advisory_xact_lock` for exactly this pattern). Two concurrent requests both commit → double booking.

**C5. Reminder task suite references columns that don't exist on `Reminder` — it crashes; reminders never send.**
`app/core/tasks.py:59,76,88,96,105,108-109,236-244` vs `app/models/reminder.py:17-29` — `scheduled_time`, `patient_id`, `message`, `channel` don't exist on the model. `AttributeError`/`TypeError` on every run; tasks retry forever via `self.retry(...)`.

**C6. `confirm_booking` is not idempotent — repeated calls create duplicate appointments.**
`app/api/v1/endpoints/booking.py:579-709` — never checks `booking.appointment_id` (already linked) or that status is still PENDING. A staff double-click creates two Appointment rows and orphans the first. `update_online_booking` (`:543-554`) allows any status transition, re-arming a confirmed booking.

---

## HIGH (16)

### Backend — Auth

**H1. ADMIN can create an OWNER / GROUP_OWNER account — full tenant takeover.**
`app/api/v1/endpoints/staff.py:46-93` — `create_staff` is guarded by `require_role(OWNER, ADMIN)` but applies no restriction on `staff_data.role` (from `UserCreate`, no whitelist). An ADMIN provisions a user with `role=OWNER` and a known password, then logs in as owner. The update path (`staff.py:127-131`) blocks the same escalation on PUT but POST is wide open.
*(Compounded by frontend finding M20: the invite dialog offers the `owner` role to any admin.)*

### Backend — Payments/Billing

**H2. Updating only `line_items` silently zeroes invoice tax.**
`app/api/v1/endpoints/billing.py:269-289` — code reads `invoice.tax_rate` via `hasattr`, but the `Invoice` model has no `tax_rate` column (only `gst_rate`, a percent, not a fraction). `hasattr` is always False → tax recomputed as `subtotal * 0` and persisted, shrinking `total` retroactively, including on paid invoices (balance goes negative). Original fractional rate is unrecoverable.

**H3. Invoice status and totals are mutable after payment, with no state-machine guard.**
`app/api/v1/endpoints/billing.py:291-293` — `setattr` loop applies `InvoiceUpdate.status` with no validation: any invoice can be set PAID with zero payments, CANCELLED resurrected to PENDING, or line items edited after payment. `delete_invoice` (line 322) doesn't check for existing payments either.

**H4. Payments accepted against CANCELLED/DRAFT invoices.**
`app/api/v1/endpoints/billing.py:413-419` — `create_payment` only verifies existence/tenant/patient. Money can be posted to a voided invoice; a payment on a CANCELLED invoice leaves status CANCELLED with growing `amount_paid` — inconsistent state that all reporting misinterprets.

**H5. Refund paths have no double-refund / partial-refund / invoice-reversal handling.**
`app/services/payment_processing.py:402-435` (Razorpay) — never checks `status == REFUNDED` before refunding again, sets full REFUNDED even for partial refunds, never records `refunded_amount`, never reverts the invoice from PAID or reduces `amount_paid`. Stripe's `process_refund` (`:200-229`) never updates local records at all. (Service layer not currently routed to HTTP.)

**H6. `update_payment_status` has no tenant scoping and no transition validation.**
`app/services/payment_service.py:100-118` — loads any payment by ID across all practices; accepts any transition (FAILED→COMPLETED etc.) without re-evaluating the invoice. A tenant-isolation gap waiting to be wired to HTTP.

### Backend — Patients/Appointments

**H7. Overlap filters ANDed instead of ORed — provider/chair conflicts in different resources undetected.**
`app/api/v1/endpoints/appointments.py:335-339, 421-427, 599-602` — with both `provider_id` and `chair_id` set, a conflict requires provider AND chair to match: same provider in a different chair, or same chair with a different provider, passes. With neither set, any overlap practice-wide triggers a spurious 409.

**H8. `PUT /appointments/{id}` skips conflict check when only provider/chair change; never tenant-validates new IDs.**
`app/api/v1/endpoints/appointments.py:409` — conflict check only runs inside the `start_time or end_time` branch. Reassigning just a provider bypasses overlap detection. Update applies `chair_id`/`provider_id` blindly (`:439-441`) — can point at another clinic's rows (global FKs) and serializes the other tenant's chair name.

**H9. Naive datetimes in the booking flow — wrong appointment instants and a guaranteed 500 on Postgres.**
`app/api/v1/endpoints/booking.py:655` (`datetime.combine` → naive stored in timestamptz, interpreted in server TZ not practice TZ); `:804-808` (`_slot_is_free` compares naive slots to tz-aware DB values → `TypeError` → public availability returns 500 whenever a non-cancelled appointment exists in the window); `:367` (server-local naive `datetime.now()` compared to UTC `submitted_at`).

**H10. No status-transition validation anywhere in the appointment/booking lifecycle.**
`app/api/v1/endpoints/appointments.py:511, 439-441`; `schemas/appointment.py:48` (client can create COMPLETED/CANCELLED appointments); `booking.py:543-554`. CANCELLED can be flipped back to CONFIRMED without re-running the conflict check; COMPLETED regresses to SCHEDULED corrupting stats; no transition matrix exists.

### Frontend (`coredent-style-main`)

**H11. Infinite refetch loop on Patient Profile and Reports pages.**
`src/hooks/useApiRequest.ts:69` memoizes `execute` on `[apiFunc, options, toast]`, but `pages/patients/PatientProfile.tsx:60-62` passes an inline options object and `pages/Reports.tsx:79-82` an inline arrow — fresh identities every render. Load effects depend on `execute` → one network round-trip per render tick forever, skeleton flashing.

**H12. Patient directory silently truncated at 100 records while header claims full count.**
`src/pages/patients/PatientList.tsx:79` sends `limit: 200` with no page param; backend clamps to 100 (`app/api/deps.py:203`). Header still renders `result.total` — 347-patient practice shows "347 in directory" but patients 101+ are unreachable and unsearchable.

**H13. Appointment times stored wrong for every non-UTC browser on /appointments (two divergent time builders).**
`src/services/appointmentsApi.ts:191-199` builds UTC from local wall-clock digits via `Date.UTC(...)`; `src/services/schedulingApi.ts:49-51` converts correctly. Same "9:00 AM" from `/appointments` on a UTC-4 browser persists as 5:00 AM local. List filters inconsistent too (`appointmentsApi.ts:141-142` sends naive strings).

**H14. Failed appointment updates report success (silent data loss).**
`src/services/schedulingApi.ts:110-112` returns `null` on PUT failure; `src/pages/Schedule.tsx:165-188` never checks and toasts "Appointment Updated". Create path swallows errors silently (`components/scheduling/AppointmentDialog.tsx:159-160`) — dialog just stops at "Saving...".

**H15. React Query cache never cleared on logout — cross-account PHI bleed.**
`src/contexts/AuthContext.tsx:264-286, 42-53` clears tokens/user but the module-level `queryClient` (`src/App.tsx:12-23`, `staleTime: 5min`) is never cleared. User B logging into the same tab within 5 minutes sees user A's cached PHI (patients, dashboard) before any refetch.

**H16. Clinical Notes patient search sends a param the backend ignores — notes can attach to the wrong patient.**
`src/pages/ClinicalNotes.tsx:123` sends `search:` but backend only reads `query` (`patients.py:39`). The picker always shows the first 8 patients of the practice regardless of typing — inviting wrong-chart clinical documentation.

---

## MEDIUM (36)

### Auth backend

- **M1.** Email-verification tokens never expire though emails claim 24h expiry — `auth.py:365-371, 707-744`; no timestamp check; link valid forever.
- **M2.** Email verification gates nothing — `auth.py:299, 314-347`; register returns full tokens with `is_email_verified=False`; flag never checked anywhere; flow is decorative.
- **M3.** Admin password reset in `update_staff` doesn't terminate sessions — `staff.py:154-161`; sets `password_changed_at` (kills access tokens) but leaves `UserSession` rows; refresh tokens keep minting new access tokens. `reset-password` does it correctly.
- **M4.** Naive/aware datetime crash in login lockout on SQLite — `auth.py:123` → 500 instead of 429 for locked users. (Same comparison was fixed in `/refresh` but not here.)
- **M5.** Refresh-token rotation race / no reuse detection — `auth.py:489-534`; no row lock, no single-use semantics; concurrent refresh both succeed; replay not treated as theft.
- **M6.** `update_staff` email change: no duplicate check (IntegrityError → 500) and no re-verification — verified flag now attests to an unverified address; enables silent identity swaps. `staff.py:136-159`.

### Payments/Billing backend

- **M7.** Tax not quantized to cents — `billing.py:208-210, 282-284`; `total` can disagree with stored `subtotal + tax` by a cent (fractional rates like 0.055).
- **M8.** Invoice numbers count-based — `billing.py:64-105`; any hard delete of a same-day invoice reissues a used number → unique-constraint 500.
- **M9.** OVERDUE invoices never transition to PARTIALLY_PAID — `billing.py:434-438`; partial payment on OVERDUE leaves it OVERDUE forever; nothing ever sets OVERDUE (dead state except via unvalidated update).
- **M10.** `get_payment_stats` revenue keyed on `Invoice.updated_at`, not payment date — `payment_service.py:171-231`; any touch re-books an old invoice into today's revenue; `today_transactions` counts invoices, not payments.
- **M11.** Float tolerance admits ₹0.99 underpayment as full settlement — `payment_processing.py:363-365`; binary floats for money.
- **M12.** Reports revenue includes DRAFT and CANCELLED invoices — `reports.py:110-125`; `total_outstanding` inflated; disagrees with billing summary.

### Patients/Appointments backend

- **M13.** `Appointment.status == 'scheduled'` lowercase literal never matches stored enum names (`'SCHEDULED'`) — `tasks.py:220` (and `'pending'` at `:58`); selects zero rows even after C5 is fixed.
- **M14.** Reminders sent for cancelled appointments — `tasks.py:66-100`; no status check before sending.
- **M15.** Soft-deleted patients remain searchable/bookable; deletion doesn't cancel future appointments — `patients.py:366, 245-266, 56-60`; `appointments.py:284-297`.
- **M16.** Duplicate-patient protection incomplete — check-then-insert race (`patients.py:185-190`); `scalar_one_or_none()` raises `MultipleResultsFound` (500) once a duplicate pair exists; `update_patient` has no duplicate check at all.
- **M17.** `AppointmentUpdate` drops create-time validators — `schemas/appointment.py:77-85`; `end_time <= start_time` and stale `duration` persistable; reschedule derives end from stale duration (`appointments.py:591`) permanently shifting times.
- **M18.** No pagination on scheduling list endpoints — `appointments.py:114-166`, `booking.py:444-479, 926-947`, `patient_portal.py:260-296`; unbounded queries with 3 eager loads each.
- **M19.** Public booking endpoint ignores most page config — `booking.py:311-441`; no business-hours check (3 AM accepted), `max_bookings_per_day` dead, allowed providers/types ignored, no slot-conflict check.
- **M20.** Public phone-verification endpoints have no rate limiting — `booking.py:1071-1098`; 6-digit code brute-forceable; plain `!=` comparison instead of `compare_digest`.
- **M21.** `GET /appointments/slots/available` crashes with TypeError on SQLite — `appointments.py:652, 689`; naive DB values vs aware slot times, uncaught.
- **M22.** Lost-update races on booking-page counters — `booking.py:277-278, 415-416`; read-modify-write instead of atomic `UPDATE ... SET x = x + 1`.

### Frontend

- **M23.** Sort-by and medical-alert filters are dead controls — `PatientList.tsx:74-80`; backend `list_patients` accepts neither param.
- **M24.** Appointments from /appointments resolve patient by name, first match wins — `appointmentsApi.ts:150-158`; no disambiguation for shared names.
- **M25.** SSN/ABHA fields non-functional but labeled "Required for US HIPAA" — `PatientDialog.tsx:325-344`; no register/state/payload; value silently discarded.
- **M26.** Patient Profile Appointments tab hardcoded empty — `PatientProfile.tsx:215` passes `appointments={[]}` though a working API exists.
- **M27.** Location/clinic switcher is a mock — `LocationSwitcher.tsx:18-33`; `MOCK_LOCATIONS`, console.log only; no query/tenant change.
- **M28.** Public booking page ignores fetched config and shows fake contact info — `PublicBooking.tsx:34-47, 75-80, 296, 601-606`; hardcoded types, fixed 14-day calendar, "123 Dental Lane, New York" on every practice's page.
- **M29.** Invoice creation: UTC-shifted due date default; tax shown but never sent — `CreateInvoiceDialog.tsx:75-77, 89, 130-138`; submitted total can differ from what user approved.
- **M30.** Receipt HTML injects unescaped patient data (stored XSS in downloaded receipt) and hardcodes a fake practice identity — `billingApi.ts:102-216`, `Billing.tsx:186-203`.
- **M31.** Patient portal swallows all fetch errors including 401 — `PatientPortal.tsx:279-312`; expired session renders "$0 outstanding" instead of re-authenticating.
- **M32.** Floating `triggerAutomation` promises reject unhandled — `Schedule.tsx:95-106,138,198`, `Billing.tsx:167-175`, `PatientDialog.tsx:180`; success toast already shown.
- **M33.** "X upcoming today" stat can never exceed 5 — `Dashboard.tsx:131-139`, `useTodayAppointments.ts:63-73`; `slice(0,5)` applied before the `> now` filter.
- **M34.** Default /appointments view is a test stub — `Appointments.tsx:62-79, 86, 243`; `data-testid` placeholder div is the default view.
- **M35.** Currency hardcoded USD everywhere despite multi-country registration and a currency setting — `useFormatters.ts:26-32` + 8 more files; IN/GB practices see `$`. `region="US"` and `US_STATES` hardcoded too.
- **M36.** Invite dialog offers `owner` role to any admin who can open it — `InviteStaffDialog.tsx:37-43`; combined with backend H1 this is the UI half of the escalation path.

---

## LOW (25)

### Auth backend

- **L1.** Login lockout counter non-atomic read-modify-write; parallel requests can exceed the attempt cap — `auth.py:133-142`; limiter keys on direct remote address (`redis_rate_limit.py:31`), wrong behind proxies.
- **L2.** Logout impossible after access token expires (15 min) — `auth.py:397-403`; requires valid access token + CSRF; client with only refresh cookie must refresh to log out.
- **L3.** Token blacklist per-process in dev; production fails *closed* on Redis error (transient outage logs out everyone); `revoke_token` failure turns logout into 500 after session deletion — `token_blacklist.py:27-28,63,75-81`, `auth.py:446`.
- **L4.** Password length validation inconsistent — schema min 8 (`schemas/auth.py:72`, `schemas/user.py:24,87`) vs policy min 12 (`config_simple.py:213`).
- **L5.** Invitation onboarding flow is dead code — schemas + `generate_invitation_token` exist, no endpoints; no force-change or change-password endpoint at all.
- **L6.** Register error handler masks any DB error as "email may already be in use" — `auth.py:303-310`.
- **L7.** Dead cookie-fallback auth path (`deps.py:44-45`, `tenant_guard.py:54`) — no endpoint sets an `access_token` cookie; would re-open CSRF if ever reached. Unused plaintext `Session.refresh_token` column retained (`models/audit.py:48`).
- **L8.** Lockout 429 with `locked_until` timestamp enables account enumeration — `auth.py:122-127`.

### Payments/Billing backend

- **L9.** `amount_paid` sums floats — `models/billing.py:92-99`; cent drift in `balance_due` with many payments.
- **L10.** Repeated `float(x/100)` money conversions; raw strings into `Enum(PaymentMethod)` columns (Razorpay `"netbanking"` would raise DataError after the invoice-paid commit) — `payment_processing.py:138,186,223,380,392`.
- **L11.** `patient_id`/`invoice_id` query params unvalidated raw strings compared to UUID columns → 500 instead of 422 — `billing.py:130-132, 351-354`.
- **L12.** Pydantic v1 `@validator` on a v2 codebase — `schemas/billing.py:24-30, 151-156`; the only line-item total and deposit checks run in compat mode.

### Patients/Appointments backend

- **L13.** Dead-weight eager load: `selectinload(Patient.appointments)` in `list_patients`, but `last_visit`/`next_appointment` don't exist on the model (always None) — `patients.py:56-60`, `schemas/patient.py:108-109`.
- **L14.** In-memory search fallback caps scan at 1000 then reports `total = len(matched)` — wrong pagination beyond 1000 — `patients.py:94, 125`.
- **L15.** Portal "upcoming appointments" includes cancelled/no-show — `patient_portal.py:273-276`; no status filter.
- **L16.** Report day-bucketing uses UTC `func.date()` while stats use practice timezone — evening appointments land on the wrong day in charts — `reports.py:54-55, 88-97`.
- **L17.** `send_daily_summary` reminder counts have no practice scoping — every practice's email includes all practices' counts — `tasks.py:157-167`.
- **L18.** No HIPAA audit logging on appointment create/update/delete (reads do log; all patient mutations log) — `appointments.py:273-380, 383-457, 460-488`.

### Frontend

- **L19.** Password policy inconsistent — Register requires 12 + classes; ResetPassword/AcceptInvitation require only 8 — `Register.tsx:28-34` vs `ResetPassword.tsx:17-27`.
- **L20.** Login ignores the deep-link redirect captured by the route guard — always `/dashboard` — `ProtectedRoute.tsx:25`, `Login.tsx:53`.
- **L21.** `useScheduling.loadData` has no request sequencing — rapid navigation can let a stale week overwrite the current one — `useScheduling.ts:25-76`.
- **L22.** Latent unstable query keys (default bounds from `new Date()` embedded in queryKey) in uncalled dashboard hooks — `useTodayAppointments.ts:46-50`, `useDashboardMetrics.ts:42-47`.
- **L23.** Public booking step-3 validation is truthiness-only — whitespace names, `a@b`, any digit string pass — `PublicBooking.tsx:157-164`.
- **L24.** PatientDialog update failures swallowed silently — `catch { /* user can retry */ }` with no toast — `PatientDialog.tsx:189-193`.
- **L25.** AppointmentDialog search skips lookup when query equals selected name — stale `patientId` can survive a re-typed identical name — `AppointmentDialog.tsx:108-112`.

---

## Recommended fix order

1. **H1 + M36** — whitelist creatable roles in `create_staff` (block OWNER/GROUP_OWNER unless caller is OWNER); restrict frontend role options by current role. *Small change, closes tenant takeover.*
2. **C4/H7/H8/H10** — scheduling concurrency: advisory lock or exclusion constraint around booking writes; fix OR-semantics overlap query; run conflict check on provider/chair-only updates with tenant validation; add a status transition matrix.
3. **C5/M13/M14/L17/L18** — rewrite the reminder task suite against the real `Reminder` model; use enum names; skip cancelled; scope summaries; add audit logging to appointment writes.
4. **C1/H2/H3/H4** — billing integrity: filter COMPLETED in summary; make mark-PAID amount-aware in one transaction; guard invoice status transitions; reject payments on CANCELLED/DRAFT.
5. **C6** — make `confirm_booking` idempotent (check `appointment_id` and PENDING status).
6. **Frontend quick wins** — H15 (`queryClient.clear()` on logout), H16 (`search`→`query` param), H12 (real pagination), H14 (check PUT result before toasting), H13 (unify the two time builders), H11 (stable `useApiRequest` deps).
7. **Timezone hardening** — M4, H9, M21, L16: standardize aware-UTC comparisons everywhere (helper that coerces naive DB values).
8. Everything Medium/Low in descending order of user impact (M30 receipt XSS, M19/M20 public booking, M10/M12 reporting accuracy, …).

## Verified as correct (no action)

JWT HS256 allow-listing with `exp`/`type` required; bcrypt-14 with legacy fallback; refresh tokens hashed at rest; access-token `iat` vs `password_changed_at` invalidation; production fail-closed secret checks; tenant guard and CORS allow-lists; invoice-number advisory lock and `FOR UPDATE` on `create_payment` (Postgres); Stripe webhook signature verification; patients export tenant scoping; DB-session rollback on exceptions; frontend refresh-rotation single-flighting.
