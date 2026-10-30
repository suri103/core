import { toURLSearchParams } from '@/lib/utils';
import { getCsrfHeader } from '@/lib/csrf';
import { logger } from '@/lib/logger';
import type { z } from 'zod';
import { validateApiResponse } from '@/lib/apiValidation';
import {
  normalizeRequestPayload,
  normalizeResponsePayload,
  shouldNormalizeContract,
} from '@/lib/domainContract';

// ... existing imports ...
import type {
  LoginCredentials,
  LoginResponse,
  User,
  InvitationDetails,
  Patient,
  PatientListParams,
  PaginatedResponse,
  Appointment,
  AppointmentListParams,
  DentalChart,
  ClinicalNote,
  ReportParams,
  ProductionReport,
  AppointmentReport,
  ApiResponse,
} from '@/types/api';
import type { BillingPreferences } from '@/types/settings';

// ============================================
// Configuration
// ============================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type ApiRecord = Record<string, unknown>;

function asApiRecord(value: unknown): ApiRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as ApiRecord
    : null;
}

function getApiErrorMessage(value: unknown, fallback: string): string {
  if (typeof value === 'string' && value.trim()) return value;
  const payload = asApiRecord(value);
  for (const key of ['message', 'detail', 'error']) {
    const candidate = payload?.[key];
    if (typeof candidate === 'string' && candidate.trim()) return candidate;
  }
  return fallback;
}

async function readResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

// ============================================
// HTTP Client
// ============================================

// SECURITY: Access tokens live in memory. Refresh credentials are issued only
// as HttpOnly cookies and are never exposed to or retained by JavaScript.
const REFRESH_TOKEN_KEY = 'cd_rt'; // retained for migration clean-up only

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;
  private isRefreshing = false;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    // Clean up any token left over from a previous build that stored it in
    // sessionStorage. This ensures upgrading users are not left with an
    // XSS-accessible token in storage.
    try {
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    } catch {
      // sessionStorage unavailable — nothing to clean up
    }
  }

  setToken(token: string | null) {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  // Compatibility no-ops for callers compiled against older clients. The
  // refresh credential is intentionally inaccessible to JavaScript.
  setRefreshToken(_token: string | null) {}

  getRefreshToken(): null {
    return null;
  }

  /**
   * Attempt to restore an authenticated session after a page reload by
   * exchanging the persisted refresh token for a fresh access token.
   * Returns true if a valid access token was obtained.
   */
  async restoreSession(): Promise<boolean> {
    // The durable credential is an HttpOnly cookie. The in-memory token is
    // only an optional compatibility fallback for an already-open tab.
    const newToken = await this.refreshAccessToken();
    return !!newToken;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retry = true,
    schema?: z.ZodSchema<T>
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    const isFormData = options.body instanceof FormData;
    const headers: HeadersInit = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    };

    // CRIT-01/CRIT-06 FIX: Use Bearer token authentication for cross-origin deployment
    // Tokens are stored in memory only (NOT localStorage, NOT cookies)
    if (this.token) {
      Object.assign(headers, {
        'Authorization': `Bearer ${this.token}`,
      });
    }

    // Add CSRF token for state-changing requests
    if (options.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method)) {
      Object.assign(headers, getCsrfHeader());
    }

    // Create AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
        // FIX: Use 'include' for cross-origin cookie support (CSRF + refresh tokens)
        credentials: 'include',
      });

      clearTimeout(timeoutId);

      // Handle 401 Unauthorized - session expired
      // But skip token refresh for login endpoints (can't refresh when not logged in)
      if (response.status === 401 && !endpoint.includes('/auth/login')) {
        if (retry) {
          const newToken = await this.refreshAccessToken();
          if (newToken) {
            // Pass the schema through — dropping it here meant retried
            // validated calls returned UNVALIDATED data with success: true.
            return this.request<T>(endpoint, options, false, schema);
          }
        }
        this.token = null;
        // Note: Tokens are in httpOnly cookies - cannot clear from client.
        // AuthProvider owns application state and route guards own navigation.
        window.dispatchEvent(new CustomEvent('auth:logout'));
        logger.warn('Session expired; authentication state cleared');
        return {
          success: false,
          error: {
            code: 'UNAUTHORIZED',
            message: 'Your session has expired. Please sign in again.',
          },
        };
      }

      // For login endpoint with 401, return invalid credentials error
      if (response.status === 401 && endpoint.includes('/auth/login')) {
        const data = await readResponseBody(response);
        return {
          success: false,
          error: {
            code: 'INVALID_CREDENTIALS',
            message: getApiErrorMessage(data, 'Invalid credentials'),
          },
        };
      }

      // Handle 403 Forbidden
      if (response.status === 403) {
        logger.warn('Access forbidden', { endpoint });
        return {
          success: false,
          error: {
            code: 'FORBIDDEN',
            message: 'You do not have permission to perform this action.',
          },
        };
      }

      const data = await readResponseBody(response)

      if (!response.ok) {
        const errorPayload = asApiRecord(data);
        const errorCode = typeof errorPayload?.code === 'string' ? errorPayload.code : 'API_ERROR';
        logger.error(`API error: ${endpoint}`, undefined, {
          endpoint,
          status: response.status,
          errorCode,
        });
        return {
          success: false,
          error: {
            code: errorCode,
            message: getApiErrorMessage(data, 'An error occurred'),
            details: errorPayload?.details && typeof errorPayload.details === 'object' && !Array.isArray(errorPayload.details)
              ? errorPayload.details as Record<string, string[]>
              : undefined,
          },
        };
      }

      // Contract normalization: the backend returns snake_case keys for the
      // core data domains; expose the stable camelCase shape to React.
      const normalizedData = shouldNormalizeContract(endpoint)
        ? normalizeResponsePayload(endpoint, data)
        : data;

      // Fail-closed: if a Zod schema is provided, validate before returning.
      // On validation failure the API surface is treated as broken — we
      // surface a structured error rather than passing malformed data into
      // the React tree.
      if (schema) {
        const validated = validateApiResponse<T>(normalizedData, schema, endpoint);
        if (validated === null) {
          return {
            success: false,
            error: {
              code: 'SCHEMA_VALIDATION_FAILED',
              message: `API response for ${endpoint} did not match the expected schema.`,
            },
          };
        }
        return { success: true, data: validated };
      }

      return {
        success: true,
        data: normalizedData as T,
      };
    } catch (error) {
      clearTimeout(timeoutId);

      // Handle timeout
      if (error instanceof Error && error.name === 'AbortError') {
        logger.error('Request timeout', error, { endpoint });
        return {
          success: false,
          error: {
            code: 'TIMEOUT_ERROR',
            message: 'Request timed out. Please try again.',
          },
        };
      }

      logger.error('Network error', error as Error, { endpoint });
      return {
        success: false,
        error: {
          code: 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : 'Network error occurred',
        },
      };
    }
  }

  async get<T>(endpoint: string, params?: Record<string, unknown>): Promise<ApiResponse<T>> {
    let url = endpoint;
    params = params && shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, params) : params;
    if (params) {
      const queryString = toURLSearchParams(params).toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }
    return this.request<T>(url, { method: 'GET' });
  }

  /**
   * GET with a Zod schema guard. On schema mismatch the response is rejected
   * with `code: 'SCHEMA_VALIDATION_FAILED'` instead of flowing malformed data
   * into the app. Use this for endpoints where a strict runtime contract
   * matters (financial, clinical, or auth-related responses).
   */
  async getValidated<T>(
    endpoint: string,
    schema: z.ZodSchema<T>,
    params?: Record<string, unknown>
  ): Promise<ApiResponse<T>> {
    let url = endpoint;
    params = params && shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, params) : params;
    if (params) {
      const queryString = toURLSearchParams(params).toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }
    return this.request<T>(url, { method: 'GET' }, true, schema);
  }

  async post<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    const normalized = shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, body) : body;
    const requestBody = normalized instanceof FormData ? normalized : normalized ? JSON.stringify(normalized) : undefined;
    return this.request<T>(endpoint, {
      method: 'POST',
      body: requestBody,
    });
  }

  async postValidated<T>(
    endpoint: string,
    schema: z.ZodSchema<T>,
    body?: unknown
  ): Promise<ApiResponse<T>> {
    const normalized = shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, body) : body;
    const requestBody = normalized instanceof FormData ? normalized : normalized ? JSON.stringify(normalized) : undefined;
    return this.request<T>(endpoint, { method: 'POST', body: requestBody }, true, schema);
  }

  async put<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    const normalized = shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, body) : body;
    const requestBody = normalized instanceof FormData ? normalized : normalized ? JSON.stringify(normalized) : undefined;
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: requestBody,
    });
  }

  async putValidated<T>(
    endpoint: string,
    schema: z.ZodSchema<T>,
    body?: unknown
  ): Promise<ApiResponse<T>> {
    const normalized = shouldNormalizeContract(endpoint) ? normalizeRequestPayload(endpoint, body) : body;
    const requestBody = normalized instanceof FormData ? normalized : normalized ? JSON.stringify(normalized) : undefined;
    return this.request<T>(endpoint, { method: 'PUT', body: requestBody }, true, schema);
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async deleteValidated<T>(
    endpoint: string,
    schema: z.ZodSchema<T>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' }, true, schema);
  }

  private async refreshAccessToken(): Promise<string | null> {
    // EXPERT HARDENING: Use JWT Rotation to prevent clinical session drops
    // We call the /auth/refresh endpoint which uses an HttpOnly cookie
    if (this.isRefreshing) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    this.refreshPromise = (async () => {
      try {
        // Create AbortController for timeout on refresh
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout for refresh

        const response = await fetch(`${this.baseUrl}/auth/refresh`, {
          method: 'POST',
          headers: {
             'Content-Type': 'application/json',
             ...getCsrfHeader() // CSRF required for state-changing refresh
          },
          // FIX: Use 'include' for cross-origin cookie support
          credentials: 'include',
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          const result = await response.json().catch(() => null) as {
            access_token?: unknown;
          } | null;
          if (!result || typeof result.access_token !== 'string' || !result.access_token) {
            return null;
          }
          this.token = result.access_token;

          // The rotated refresh token arrives only through Set-Cookie.
          return this.token;
        }

        return null;
      } catch (err) {
        // Handle timeout specifically
        if (err instanceof Error && err.name === 'AbortError') {
          logger.error('Token refresh timeout', err);
        } else {
          logger.error('Failed to rotate access token', err as Error);
        }
        return null;
      } finally {
        this.isRefreshing = false;
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

// ============================================
// Zod schemas for security-sensitive responses
// ============================================
// Keep these co-located with the api client; only the responses we want to
// validate strictly are listed here.

import { z as zod } from 'zod';

const loginResponseSchema = zod.object({
  access_token: zod.string().min(1),
  refresh_token: zod.string().min(1).optional(),
  token_type: zod.string().min(1),
  expires_in: zod.number().int().positive(),
  csrf_token: zod.string().min(1),
  must_change_password: zod.boolean().optional(),
});

// The backend serializes ORM/Pydantic fields in snake_case. Accept both
// shapes at this boundary and expose one stable camelCase shape to React.
const userSchema = zod.object({
  id: zod.string().min(1),
  email: zod.string().email(),
  firstName: zod.string().min(1).optional(),
  first_name: zod.string().min(1).optional(),
  lastName: zod.string().min(1).optional(),
  last_name: zod.string().min(1).optional(),
  full_name: zod.string().min(1).optional(),
  role: zod.string().min(1),
  practiceId: zod.string().min(1).optional(),
  practice_id: zod.string().min(1).optional(),
  practiceName: zod.string().optional(),
  practice_name: zod.string().optional(),
  practiceCountry: zod.string().optional(),
  practice_country: zod.string().optional(),
  practiceCurrency: zod.string().optional(),
  practice_currency: zod.string().optional(),
}).passthrough()
  .superRefine((raw, ctx) => {
    if (!(raw.firstName ?? raw.first_name) || !(raw.lastName ?? raw.last_name)) {
      ctx.addIssue({ code: zod.ZodIssueCode.custom, message: 'User name is missing' });
    }
    if (!(raw.practiceId ?? raw.practice_id)) {
      ctx.addIssue({ code: zod.ZodIssueCode.custom, message: 'Practice id is missing' });
    }
  })
  .transform((raw) => ({
    ...raw,
    firstName: raw.firstName ?? raw.first_name!,
    lastName: raw.lastName ?? raw.last_name!,
    role: raw.role.toLowerCase(),
    practiceId: raw.practiceId ?? raw.practice_id!,
    practiceName: raw.practiceName ?? raw.practice_name ?? '',
    practiceCountry: raw.practiceCountry ?? raw.practice_country ?? 'US',
    practiceCurrency: raw.practiceCurrency ?? raw.practice_currency ?? undefined,
    mustChangePassword: raw.must_change_password ?? raw.mustChangePassword ?? false,
  }));

// ============================================
// Auth API
// ============================================

export const authApi = {
  login: (credentials: LoginCredentials) =>
    apiClient.postValidated<LoginResponse>(
      '/auth/login',
      loginResponseSchema as unknown as zod.ZodType<LoginResponse>,
      credentials,
    ),

  register: (data: {
    practice_name: string;
    first_name: string;
    last_name: string;
    email: string;
    password: string;
    country?: string;
    phone?: string;
  }) => apiClient.post<{ message: string }>('/auth/register', data),

  logout: () =>
    apiClient.post<void>('/auth/logout', {}), // Token from httpOnly cookie

  getCurrentUser: () =>
    apiClient.getValidated<User>('/auth/me', userSchema as unknown as zod.ZodType<User>),

  getCsrf: () =>
    apiClient.get<{ csrf_token: string }>('/auth/csrf'),

  // Restore session after a page reload using the HttpOnly refresh cookie
  restoreSession: () =>
    apiClient.restoreSession(),

  setToken: (token: string | null) =>
    apiClient.setToken(token),

  setRefreshToken: (token: string | null) =>
    apiClient.setRefreshToken(token),

  getRefreshToken: () =>
    apiClient.getRefreshToken(),

  validateInvitation: (token: string) =>
    apiClient.post<InvitationDetails>('/auth/invitations/validate', { token }),

  acceptInvitation: (data: { token: string; password: string }) =>
    apiClient.post<void>('/auth/invitations/accept', data),

  requestPasswordReset: (data: { email: string }) =>
    apiClient.post<void>('/auth/forgot-password', data),

  resetPassword: (data: { token: string; password: string }) =>
    apiClient.post<void>('/auth/reset-password', data),

  verifyEmail: (token: string) =>
    apiClient.post<{ message: string }>('/auth/verify-email', { token }),

  changePassword: (data: { current_password: string; new_password: string }) =>
    apiClient.postValidated<LoginResponse>(
      '/auth/change-password',
      loginResponseSchema as unknown as zod.ZodType<LoginResponse>,
      data,
    ),
};

export const settingsApi = {
  getBillingPreferences: () =>
    apiClient.get<BillingPreferences>('/settings/billing'),

  updateBillingPreferences: (data: BillingPreferences) =>
    apiClient.put<BillingPreferences>('/settings/billing', data),
};

// M6 FIX: notificationsApi removed — it called /notifications/unread-count,
// a route that has never existed in the backend router registry.

// ============================================
// Patients API
// ============================================

export const patientsApi = {
  list: (params?: PatientListParams) => {
    // The backend list endpoint reads `query` (not `search`); translate at
    // this boundary so patient pickers actually filter instead of showing the
    // practice's first page regardless of the typed term.
    const { search, ...rest } = params ?? {};
    return apiClient.get<PaginatedResponse<Patient>>(
      '/patients',
      (search ? { query: search, ...rest } : rest) as unknown as Record<string, unknown>,
    );
  },

  getById: (id: string) =>
    apiClient.get<Patient>(`/patients/${id}`),

  create: (patient: Omit<Patient, 'id' | 'createdAt' | 'updatedAt'>) =>
    apiClient.post<Patient>('/patients', patient),

  update: (id: string, patient: Partial<Patient>) =>
    apiClient.put<Patient>(`/patients/${id}`, patient),

  delete: (id: string) =>
    apiClient.delete<void>(`/patients/${id}`),

  // L3 FIX: typed as a structural record instead of `any` — the backend
  // returns PatientExportResponse (patient + related collections).
  exportData: (id: string) =>
    apiClient.get<Record<string, unknown>>(`/patients/${id}/export`),
};

// ============================================
// Appointments API
// ============================================

export const appointmentsApi = {
  list: async (params: AppointmentListParams) => {
    // The backend list endpoint returns the `{ appointments, count }` envelope;
    // unwrap it to the `Appointment[]` the scheduling/dashboard hooks consume.
    const res = await apiClient.get<{ appointments: Appointment[]; count: number }>(
      '/appointments',
      params as unknown as Record<string, unknown>,
    );
    if (res.success && res.data && Array.isArray(res.data.appointments)) {
      return { ...res, data: res.data.appointments };
    }
    return { ...res, data: [] as Appointment[] };
  },

  getById: (id: string) =>
    apiClient.get<Appointment>(`/appointments/${id}`),

  create: (appointment: Omit<Appointment, 'id' | 'createdAt' | 'updatedAt'>) =>
    apiClient.post<Appointment>('/appointments', appointment),

  update: (id: string, appointment: Partial<Appointment>) =>
    apiClient.put<Appointment>(`/appointments/${id}`, appointment),

  delete: (id: string) =>
    apiClient.delete<void>(`/appointments/${id}`),
};

// ============================================
// Dental Chart API
// ============================================

export const dentalChartApi = {
  getByPatientId: (patientId: string) =>
    apiClient.get<DentalChart>(`/patients/${patientId}/chart`),

  update: (patientId: string, chart: Partial<DentalChart>) =>
    apiClient.put<DentalChart>(`/patients/${patientId}/chart`, chart),
};

// ============================================
// Clinical Notes API
// ============================================

export const clinicalNotesApi = {
  listByPatient: (patientId: string) =>
    apiClient.get<ClinicalNote[]>(`/patients/${patientId}/notes`),

  getById: (id: string) =>
    apiClient.get<ClinicalNote>(`/notes/${id}`),

  create: (note: Omit<ClinicalNote, 'id' | 'createdAt' | 'updatedAt'>) =>
    apiClient.post<ClinicalNote>('/notes', note),

  update: (id: string, note: Partial<ClinicalNote>) =>
    apiClient.put<ClinicalNote>(`/notes/${id}`, note),

  delete: (id: string) =>
    apiClient.delete<void>(`/notes/${id}`),
};

// Treatment plans use the explicit wire adapters in services/treatmentPlanApi.ts.
// Keeping a second generic API here previously exposed routes that do not exist.

// ============================================
// Reports API
// ============================================

export const reportsApi = {
  getProduction: (params: ReportParams) =>
    apiClient.get<ProductionReport>('/reports/production', params as unknown as Record<string, unknown>),

  getAppointments: (params: ReportParams) =>
    apiClient.get<AppointmentReport>('/reports/appointments', params as unknown as Record<string, unknown>),
};

// L3 FIX: the legacy billingApi block (POST /invoices, /payments,
// /patients/{id}/ledger) was removed — those paths do not exist in the
// backend (billing lives under /billing/...) and no page imported this
// object; the live client is src/services/billingApi.ts.
