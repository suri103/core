// ============================================
// CoreDent PMS - Domain Payload Contracts
// ============================================
// Single boundary where the camelCase React layer meets the snake_case
// FastAPI wire contract for the core data domains. Centralising this here
// keeps `services/api.ts` purely mechanical and lets the per-domain
// structural adapters (e.g. the patients flat-address -> nested-address map)
// live beside the generic key-case conversion.
//
// See docs/PAYLOAD_CONTRACT_AUDIT.md for the per-domain contract matrix.

import { camelToSnake, snakeToCamel } from './keyCase';

// LIVE ROUTES (verified vs coredent-api/app/api/v1/api.py + treatment.py,
// billing.py): /patients, /appointments, /notes, /billing/invoices,
// /billing/payments, /billing, /staff, /patients/{id}/chart.
// Dead prefixes (/treatment-plans, /invoices, /payments, /dental-chart) were
// removed — they never matched and misled the next endpoint author.
//
// /treatment/* is intentionally NOT normalized: services/treatmentPlanApi.ts
// owns a typed snake_case -> domain adapter for those payloads. Running the
// generic camelCase conversion first double-converted every key, so the
// adapter read plan_name/ada_code/... as undefined and blanked the whole
// domain (treatmentPlanApi.test.ts caught it).
const NORMALIZED_PREFIXES = [
  '/patients',
  '/appointments',
  '/notes',
  '/billing',
  '/staff',
  '/clinical',
  '/communications',
  '/providers',
  '/chairs',
  '/appointment-types',
];

/**
 * True when an endpoint belongs to a domain whose payload contract is
 * normalised at this boundary (patients, appointments, clinical notes,
 * billing, staff, communications). Auth, public booking, patient portal and
 * insurance keep their existing snake_case (or audited) wire format.
 */
export function shouldNormalizeContract(endpoint: string): boolean {
  // The GET helpers append query strings (and possibly a hash) before the
  // request() step that consults this predicate. Strip them so a paged/list
  // endpoint like "/patients?page=1&limit=10" still resolves to the /patients
  // prefix and gets its response normalized.
  const cleanEndpoint = endpoint.split('?')[0].split('#')[0];
  return NORMALIZED_PREFIXES.some((prefix) =>
    cleanEndpoint === prefix || cleanEndpoint.startsWith(`${prefix}/`),
  );
}

// ---------------------------------------------------------------------------
// Patients structural adapter
// ---------------------------------------------------------------------------
// Backend PatientResponse serialises address fields flat (address_street,
// address_city, ...); the React Patient type uses a nested `address` object.
// emergency_contact/insurance_info are JSON columns that already normalise to
// emergencyContact/insuranceInfo via the generic key-case conversion.

type PatientLike = Record<string, unknown>;

function has(addressPart: unknown): boolean {
  return addressPart !== undefined && addressPart !== null && addressPart !== '';
}

function groupPatientAddress(record: PatientLike): PatientLike {
  const street = record.addressStreet;
  const city = record.addressCity;
  const state = record.addressState;
  const zip = record.addressZip;
  if (has(street) || has(city) || has(state) || has(zip)) {
    record.address = {
      street: typeof street === 'string' ? street : '',
      city: typeof city === 'string' ? city : '',
      state: typeof state === 'string' ? state : '',
      zipCode: typeof zip === 'string' ? zip : '',
    };
  }
  delete record.addressStreet;
  delete record.addressCity;
  delete record.addressState;
  delete record.addressZip;
  return record;
}

function flattenPatientAddress(record: PatientLike): PatientLike {
  const address = record.address;
  if (address && typeof address === 'object' && !Array.isArray(address)) {
    const parts = address as PatientLike;
    // camelToSnake runs before this adapter, so nested keys are already in
    // snake_case (zipCode -> zip_code); accept both dialects defensively.
    if (has(parts.street)) record.address_street = String(parts.street);
    if (has(parts.city)) record.address_city = String(parts.city);
    if (has(parts.state)) record.address_state = String(parts.state);
    if (has(parts.zipCode) || has(parts.zip_code)) {
      record.address_zip = String(parts.zip_code ?? parts.zipCode ?? '');
    }
  }
  delete record.address;
  return record;
}

function adaptPatientList(items: unknown[]): unknown[] {
  return items.map((item) =>
    item && typeof item === 'object' && !Array.isArray(item)
      ? groupPatientAddress({ ...(item as PatientLike) })
      : item,
  );
}

function adaptPatientResponseDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => adaptPatientResponseDeep(item));
  }
  if (!value || typeof value !== 'object') return value;
  const record = value as PatientLike;
  const next = { ...record };
  groupPatientAddress(next);

  // The backend list envelope is { items, total, page, limit, pages }, while
  // existing React consumers use the legacy { data, totalPages } shape.
  // Prefer an existing data array to preserve legacy callers, otherwise
  // project the backend items array into the established frontend contract.
  const patientList = Array.isArray(next.data)
    ? next.data
    : Array.isArray(next.items)
      ? next.items
      : null;
  if (patientList) {
    next.data = adaptPatientList(patientList);
  }
  if (next.totalPages === undefined && typeof next.pages === 'number') {
    next.totalPages = next.pages;
  }

  return next;
}

function adaptPatientRequest(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => adaptPatientRequest(item));
  }
  if (!value || typeof value !== 'object') return value;
  const record = { ...(value as PatientLike) };
  return flattenPatientAddress(record);
}

// ---------------------------------------------------------------------------
// Public entry points used by the ApiClient
// ---------------------------------------------------------------------------

/**
 * Normalise an outgoing JSON request body (or query-param object) from the
 * React camelCase dialect to the backend snake_case wire format.
 */
export function normalizeRequestPayload<T>(endpoint: string, body: T): T {
  if (body instanceof FormData || body instanceof File || body instanceof Blob) {
    return body;
  }
  const converted = camelToSnake(body);
  if (endpoint.startsWith('/patients')) {
    return adaptPatientRequest(converted) as unknown as T;
  }
  return converted;
}

/**
 * Normalise an incoming JSON response body from the backend snake_case wire
 * format to the stable camelCase shape used across the React layer.
 */
export function normalizeResponsePayload<T>(endpoint: string, data: T): T {
  const converted = snakeToCamel(data);
  if (endpoint.startsWith('/patients')) {
    return adaptPatientResponseDeep(converted) as unknown as T;
  }
  return converted;
}