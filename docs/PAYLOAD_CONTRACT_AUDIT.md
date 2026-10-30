# Payload Contract Audit & Normalization

**Status:** normalized at the frontend boundary for the core data domains
**Last updated:** 2026-08-09

## 1. The contract problem

The FastAPI backend serializes Pydantic models with **snake_case** field names
on the wire (`first_name`, `date_of_birth`, `invoice_number`, ...). The React
layer uses one stable **camelCase** shape (`firstName`, `dateOfBirth`,
`invoiceNumber`, ...), which is what `src/types/*`, the service tests, and
`API.md` document.

Previously the two dialects met nowhere: React components sent camelCase JSON
bodies that the snake_case schemas rejected or silently dropped, and expected
camelCase responses the snake_case serializers never produced. This is the
boundary the normalization closes.

## 2. Normalization boundary (implemented)

| File | Responsibility |
|---|---|
| `src/lib/keyCase.ts` | Recursive `snakeToCamel`/`camelToSnake` key transforms (idempotent for keys already in the target dialect). |
| `src/lib/domainContract.ts` | `shouldNormalizeContract(endpoint)`, `normalizeRequestPayload(endpoint, body)`, `normalizeResponsePayload(endpoint, data)` + the patients flat-address ⇄ nested-address structural adapter. |
| `src/services/api.ts` | Applies the boundary on every `get/getValidated/post/postValidated/put/putValidated/delete` for the normalized domains — query params, JSON bodies (camel→snake) and JSON responses (snake→camel). FormData is passed through untouched. |

**Normalized domains (prefix allow-list, as implemented in `NORMALIZED_PREFIXES`):**
`/patients`, `/appointments`, `/notes`, `/billing`, `/staff`, `/clinical`,
`/communications`, `/providers`, `/chairs`, `/appointment-types`.

**Explicitly exempt** (their frontend contract already mirrors the backend
snake_case verbatim and was audited as-is): `/auth/*`, `/booking/*`,
`/portal/*`, `/insurance/*`. `/treatment/*` is exempt because
`services/treatmentPlanApi.ts` owns a typed snake_case ⇄ domain adapter, and
running the generic conversion first double-converted every key.

**Corrections applied 2026-10-18** (this document described a boundary the code
did not have):

- The normalized list previously named `/treatment-plans`, `/invoices`,
  `/payments` and `/dental-chart`. None of those prefixes exist — the first three
  were removed as dead (invoices and payments live under `/billing`) — so the
  document listed domains that were never normalized.
- `/communications/*` was listed as exempt on the claim that its frontend
  contract "already mirrors the backend snake_case verbatim". It did not: the
  Communications page and `communicationsApi` types are camelCase, so template
  and reminder creates failed with 422, updates returned 200 while writing
  nothing, and the conversations list threw on `patientId`. It is normalized now.

## 3. Per-domain matrix

### Patients — ✅ normalized (case + address structure)
| | Backend wire (snake_case) | Frontend type (camelCase) |
|---|---|---|
| Identity | `id`, `first_name`, `last_name`, `full_name`, `date_of_birth` | `id`, `firstName`, `lastName`, `dateOfBirth` |
| Contact | `email`, `phone` | `email`, `phone` |
| Address | `address_street`, `address_city`, `address_state`, `address_zip` (flat) | `address: { street, city, state, zipCode }` (nested) |
| Extra | `emergency_contact`, `insurance_info`, `has_medical_alerts` | `emergencyContact`, `insuranceInfo`, `hasMedicalAlerts` |

The patients adapter additionally **groups** the four flat `address_*` fields
into the nested `address` object on responses and **flattens** it back into
`address_*` keys on request bodies. List responses (`PaginatedResponse`) are
handled recursively inside `{ data: [...] }`.

### Appointments — ✅ normalized (case + response mapper)
| | Backend wire | Frontend (`types/api.ts`) |
|---|---|---|
| Naming | `patient_id`, `provider_id`, `start_time`, `end_time`, `appointment_type` + `type` (alias) | `patientId`, `providerId`, `startTime`, `endTime`, `type` |
| Structure | `chair_id` + `operatory_id`/`operatory_name`, `patient_name`/`provider_name`, `duration`, `status` (enum values `scheduled`/`checked_in`/…) | `operatoryId`/`operatoryName`, `patientName`/`providerName`, `status` (same enum values) |

The backend `AppointmentResponse` now emits the read-model aliases `type`,
`patient_name`, `provider_name`, `operatory_id`/`operatory_name` (populated
from the eager-loaded patient/provider/chair relationships via
`_serialize_appointment`), so the frontend contract closes purely through the
existing snake_case→camelCase boundary — `type` and `appointment_type` both
present, `operatoryId`/`operatoryName` populated, and the `status`/`type` enum
value sets match the backend exactly (`AppointmentStatus` 1:1; frontend
`AppointmentType` gained `whitening`). `appointmentsApi.list` (in `api.ts`)
unwraps the backend `{appointments, count}` envelope into `Appointment[]`,
mirroring the `billingApi.getInvoices` fix. A second, narrower `Appointment`
shape in `src/services/appointmentsApi.ts` (patient/patientName/time/duration)
remains a separate scheduling-read model unrelated to `AppointmentCreate`.

### Clinical notes — ✅ normalized + backend implemented
`src/services/api.ts` `clinicalNotesApi` calls `GET|POST|PUT|DELETE /notes`
and `GET /patients/:id/notes`. These routes now exist in
`coredent-api/app/api/v1/endpoints/clinical_notes.py`: tenant-scoped CRUD with
`ClinicalNoteCreate`↔`ClinicalNoteUpdate`↔`ClinicalNoteResponse` Pydantic
schemas. The backend `ClinicalNote` model was extended with the SOAP columns
`subjective`/`objective`/`assessment`/`plan` (plus `content`/`attachments`),
and `NoteType` now covers `soap`/`procedure`/`treatment`/etc., so the frontend
`type` contract (`soap`|`procedure`|`general`) maps onto a real enum member.
`clinicalNotesApi.listByPatient` → `GET /patients/:id/notes`; create/update/delete
→ `/notes` and `/notes/:id`; the wire `type` field is coerced to the enum on
bind (`NoteType(...)`) so no value is silently dropped. `/notes` stays in the
normalized prefix list, so these routes inherit the same camelCase↔snake_case
contract guarantees as patients/appointments.
### Billing — ✅ normalized (case); shapes differ
| | Backend wire | Frontend (`types/billing.ts`) |
|---|---|---|
| Invoice | `invoice_number`, `line_items`, `amount_paid`, `amount_due`, `issue_date`, `due_date`, `tax_rate`/`tax_amount` | `invoiceNumber`, `lineItems`, `amountPaid`, `balance`/`amountDue`, `issueDate`/`dueDate`, `taxRate`/`taxAmount` |
| Line item | `procedure_code`, `unit_price`, `discount` | `procedureCode`, `unitPrice`, `discount` |

Case conversion covers the naming. Two shape notes: the frontend derives
`taxAmount` from `taxRate` in some render paths while the backend stores both,
and `getInvoices` returns `InvoiceListResponse` (`{invoices, count}`) while
`billingApi.getInvoices` types the payload as a bare array — the receiving
layer must unwrap `response.data.invoices`. Filter params are normalized
(`patientId` → `patient_id`, matching `list_invoices`).

### Staff — case normalized; pagination mismatch documented
| | Backend wire | Frontend (`types/staff.ts`) |
|---|---|---|
| Member | `first_name`, `last_name`, `is_active`, `created_at`, `updated_at` | `firstName`, `lastName`, `status`/`is_active` in `UpdateStaffRequest`, `createdAt` |
| List | `GET /staff` returns a bare `List[UserResponse]` | `staffApi.list()` types the response as `PaginatedResponse<StaffMember>` (`{data, total, …}`) |

Case conversion is handled. **Mismatch:** the backend staff list is a plain
array while the frontend expects the paginated envelope — `data` would be
`undefined` at runtime. Requires either a backend `PaginatedResponse` wrapper
or a frontend unwrap at the service boundary (follow-up).

## 4. Behavior guarantees

- **Idempotent transforms**: a payload already in the target dialect passes
  through unchanged (no `_` ⇄ uppercase churn).
- **Auth contract untouched**: `LoginResponse`/registration keep their
  literal snake_case keys (`access_token`, `csrf_token`, …) exactly as
  `AuthContext` and the Zod schemas consume them.
- **FormData untouched**: multipart uploads (`/patients/:id/attachments`)
  are never JSON-serialized or key-rewritten.
- **Fail-closed**: when a Zod schema is supplied the schema validates the
  *normalized* payload, so React receives the stable camelCase shape.

## 5. Test coverage

- `src/lib/__tests__/keyCase.test.ts` — key + recursive transform coverage.
- `src/lib/__tests__/domainContract.test.ts` — scoping, address flatten/nest,
  pagination recurse, FormData passthrough, exemption list.
- `src/services/__tests__/api.test.ts` — end-to-end through `ApiClient`:
  snake→camel responses, address grouping, camel→snake request bodies,
  auth exemption, 401-refresh retry, and 204 handling.
- `src/services/__tests__/patientsApi.test.ts` — create/update now assert the
  snake_case wire payload (proving the boundary conversion).

## 6. Residual follow-ups (status updated 2026-08-09)

### Resolved in this pass

2. **Staff list envelope — ✅ FIXED (frontend service boundary).** `staffApi.list()`
   now normalizes either wire dialect — the backend's bare `List[UserResponse]`
   or a paginated envelope — into the `PaginatedResponse<StaffMember>` shape the
   UI reads, and maps backend `is_active`/`last_login` onto `status`/`lastLoginAt`.
3. **Invoices list envelope — ✅ FIXED (frontend service boundary).**
   `billingApi.getInvoices()` now unwraps the backend `InvoiceListResponse
   {invoices, count}` (and tolerates a bare array) so the UI receives the
   `Invoice[]` it iterates. Tests updated to the real envelope shape.
4. **Clinical notes — ✅ FIXED (backend + schema).** Added tenant-scoped CRUD
   routes `GET|POST|PUT|DELETE /notes` and `GET /patients/{id}/notes` in
   `endpoints/clinical_notes.py`, the `ClinicalNote` SOAP columns
   (`subjective`/`objective`/`assessment`/`plan`), the matching
   `ClinicalNoteCreate`/`ClinicalNoteUpdate`/`ClinicalNoteResponse` schemas, and
   extended `NoteType` so the frontend `type` (`soap`/`procedure`/`general`)
   maps onto real enum values. The `/notes` normalized prefix now resolves to
   live routes with snake_case payloads — full-stack contract closed.
5. **Appointments shape — ✅ FIXED (backend response mapper + envelope).**
   `AppointmentResponse` now emits the read-model aliases `type`,
   `patient_name`, `provider_name`, `operatory_id`/`operatory_name` (built by
   `_serialize_appointment` from eager-loaded relationships), `chair_id ⇄
   operatoryId` and `type ⇄ appointment_type` are bridged, and the frontend
   `AppointmentStatus`/`AppointmentType` unions match the backend enums
   (`whitening` added). `appointmentsApi.list` unwraps `{appointments, count}`.
   Covered by `tests/test_appointments_contract.py` and an `api.test.ts`
   envelope test.
6. **Scheduling support — ✅ FIXED (missing backend routes + service wiring).**
   The Schedule page's `schedulingApi` hit routes that did not exist. Added the
   tenant-scoped `/providers`, `/chairs`, `/appointment-types`
   (`endpoints/references.py`), `/patients/search` (patients type-ahead),
   and `/appointments/{id}/status|cancel|reschedule` action routes, plus the
   `/providers`/`/chairs`/`/appointment-types` normalization prefixes.
   `schedulingApi` now unwraps the `{appointments, count}` list envelope and
   maps ISO start/end times; `appointmentsApi` (Appointments page) translates
   the single-day `date` filter to `start_date`/`end_date`, resolves patient
   names into IDs via `/patients/search` on create/update, and normalizes
   statuses. `AppointmentCreate`/`Update` coerce human-readable type names
   ("Checkup", "Root Canal", "Follow-up") onto the `AppointmentTypeEnum`.
   Covered by `tests/test_scheduling_reference.py`, `schedulingApi.test.ts`
   and the rewritten `appointmentsApi.test.ts`.
7. **Patient export — ✅ FIXED (schema + route order).** `/patients/{id}/export`
   was shadowed by `GET /patients/{patient_id}` (UUID validation → 422). The
   GET-by-id route now sits below `/export`, `/search` and `/notes`, and the
   hand-rolled payload is formalised with the `PatientExportResponse` Pydantic
   schema (typed envelope/actor/timestamps, portable per-section rows).

### Closed

The `/patients/{id}/export` hand-rolled `model_to_dict` payload was
formalised with the `PatientExportResponse` Pydantic schema and the route was
un-shadowed by moving `GET /patients/{patient_id}` below `/export`, `/search`
and `/notes`. No schema-only gaps remain — every core data domain in this
audit is now normalised at the frontend boundary with matching backend routes.