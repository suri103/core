import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  apiClient,
  appointmentsApi,
  authApi,
  clinicalNotesApi,
  dentalChartApi,
  patientsApi,
  reportsApi,
  settingsApi,
} from '../api';

const jsonResponse = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

const loginBody = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
  expires_in: 900,
  csrf_token: 'csrf-token',
};

const userBody = {
  id: 'user-1',
  email: 'owner@example.com',
  firstName: 'Owner',
  lastName: 'User',
  role: 'owner',
  practiceId: 'practice-1',
  practiceName: 'Core Dental',
};

const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
  const url = String(input);

  if (url.endsWith('/auth/login') || url.endsWith('/auth/register')) {
    return jsonResponse(loginBody);
  }

  if (url.endsWith('/auth/me')) {
    return jsonResponse(userBody);
  }

  if (url.endsWith('/auth/refresh')) {
    return jsonResponse({ access_token: 'rotated-token' });
  }

  return jsonResponse({ ok: true });
});

describe('api surface request contracts', () => {
  beforeEach(() => {
    fetchMock.mockClear();
    vi.stubGlobal('fetch', fetchMock);
    apiClient.setToken(null);
    authApi.setRefreshToken(null);
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    apiClient.setToken(null);
    authApi.setRefreshToken(null);
    sessionStorage.clear();
  });

  it('manages auth tokens and calls auth endpoints through validated client methods', async () => {
    authApi.setToken('access-token');
    authApi.setRefreshToken('refresh-token');

    expect(authApi.getRefreshToken()).toBeNull();
    expect(apiClient.getToken()).toBe('access-token');

    await expect(authApi.login({ email: 'owner@example.com', password: 'Password123!' })).resolves.toMatchObject({ success: true });
    await expect(authApi.register({
      practice_name: 'Core Dental',
      first_name: 'Owner',
      last_name: 'User',
      email: 'owner@example.com',
      password: 'Password123!',
    })).resolves.toMatchObject({ success: true });
    await expect(authApi.getCurrentUser()).resolves.toMatchObject({ success: true });
    await expect(authApi.restoreSession()).resolves.toBe(true);
    await expect(authApi.logout()).resolves.toMatchObject({ success: true });
    await expect(authApi.validateInvitation('invite-token')).resolves.toMatchObject({ success: true });
    await expect(authApi.acceptInvitation({ token: 'invite-token', password: 'Password123!' })).resolves.toMatchObject({ success: true });
    await expect(authApi.requestPasswordReset({ email: 'owner@example.com' })).resolves.toMatchObject({ success: true });
    await expect(authApi.resetPassword({ token: 'reset-token', password: 'Password123!' })).resolves.toMatchObject({ success: true });

    const requestedUrls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(requestedUrls).toEqual(expect.arrayContaining([
      '/api/v1/auth/login',
      '/api/v1/auth/register',
      '/api/v1/auth/me',
      '/api/v1/auth/refresh',
      '/api/v1/auth/logout',
      '/api/v1/auth/invitations/validate',
      '/api/v1/auth/invitations/accept',
      '/api/v1/auth/forgot-password',
      '/api/v1/auth/reset-password',
    ]));
  });

  it('builds patient, appointment, clinical, treatment, billing, and report requests', async () => {
    await patientsApi.list({ search: 'ada', page: 2, limit: 10 });
    await patientsApi.getById('patient-1');
    await patientsApi.create({ firstName: 'Ada' } as never);
    await patientsApi.update('patient-1', { lastName: 'Lovelace' } as never);
    await patientsApi.delete('patient-1');

    await appointmentsApi.list({ patientId: 'patient-1', startDate: '2026-06-01', endDate: '2026-06-30' } as never);
    await appointmentsApi.getById('appointment-1');
    await appointmentsApi.create({ patientId: 'patient-1' } as never);
    await appointmentsApi.update('appointment-1', { status: 'confirmed' } as never);
    await appointmentsApi.delete('appointment-1');

    await dentalChartApi.getByPatientId('patient-1');
    await dentalChartApi.update('patient-1', { teeth: [] } as never);

    await clinicalNotesApi.listByPatient('patient-1');
    await clinicalNotesApi.getById('note-1');
    await clinicalNotesApi.create({ patientId: 'patient-1', content: 'Stable' } as never);
    await clinicalNotesApi.update('note-1', { content: 'Updated' } as never);
    await clinicalNotesApi.delete('note-1');

    // M6/L3 FIX: legacy billingApi (POST /invoices, /payments, ledger) and
    // notificationsApi were removed — those wire paths never existed in the
    // backend router registry. The live billing client is
    // src/services/billingApi.ts and is covered by its own test file.

    await reportsApi.getProduction({ startDate: '2026-06-01', endDate: '2026-06-30' } as never);
    await reportsApi.getAppointments({ startDate: '2026-06-01', endDate: '2026-06-30' } as never);

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/patients?query=ada&page=2&limit=10', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/patients/patient-1', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/appointments/appointment-1', expect.objectContaining({ method: 'DELETE' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/patients/patient-1/chart', expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/notes/note-1', expect.objectContaining({ method: 'DELETE' }));
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/treatment-plans'))).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/reports/appointments?startDate=2026-06-01&endDate=2026-06-30', expect.objectContaining({ method: 'GET' }));
  });

  it('builds settings and low-level validated requests', async () => {
    await settingsApi.getBillingPreferences();
    await settingsApi.updateBillingPreferences({ invoicePrefix: 'CD' } as never);

    await apiClient.post('/form-data', new FormData());
    await apiClient.put('/form-data/1', new FormData());
    await apiClient.deleteValidated('/delete-validated', { parse: (value: unknown) => value } as never);

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/settings/billing', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/settings/billing', expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/form-data', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/form-data/1', expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/delete-validated', expect.objectContaining({ method: 'DELETE' }));
  });
});