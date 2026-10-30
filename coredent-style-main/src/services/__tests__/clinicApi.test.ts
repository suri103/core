import { describe, it, expect, beforeEach } from 'vitest';
import { clinicApi } from '../clinicApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { ClinicSettings } from '@/types/clinic';

const closedDay = { isOpen: false, openTime: '09:00', closeTime: '17:00' };
const openDay = { isOpen: true, openTime: '09:00', closeTime: '17:00' };

const mockSettings: ClinicSettings = {
  id: 'clinic-1',
  name: 'CoreDent Family Dentistry',
  email: 'office@example.com',
  phone: '555-1234',
  address: {
    street: '123 Dental Way',
    city: 'Springfield',
    state: 'IL',
    zipCode: '62701',
    country: 'USA',
  },
  workingHours: {
    monday: openDay,
    tuesday: openDay,
    wednesday: openDay,
    thursday: openDay,
    friday: openDay,
    saturday: closedDay,
    sunday: closedDay,
  },
  chairs: [],
  appointmentTypes: [],
  timezone: 'America/Chicago',
  dateFormat: 'MM/DD/YYYY',
  currency: 'USD',
  updatedAt: '2026-06-01T00:00:00Z',
};

describe('clinicApi', () => {
  beforeEach(() => server.resetHandlers());

  it('getSettings returns clinic settings', async () => {
    server.use(
      http.get('/api/v1/settings', () => HttpResponse.json(mockSettings)),
    );
    const result = await clinicApi.getSettings();
    expect(result.data?.name).toBe('CoreDent Family Dentistry');
  });

  it('updateSettings sends a PUT', async () => {
    server.use(
      http.put('/api/v1/settings', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockSettings, ...body });
      }),
    );
    const result = await clinicApi.updateSettings({ name: 'New Name' });
    expect(result.data?.name).toBe('New Name');
  });

  it('uploadLogo posts FormData and returns a URL', async () => {
    server.use(
      http.post('/api/v1/settings/logo', () =>
        HttpResponse.json({ url: 'https://blob.example.com/logo.png' }, { status: 201 }),
      ),
    );
    const file = new File(['x'], 'logo.png', { type: 'image/png' });
    const result = await clinicApi.uploadLogo(file);
    expect(result.data?.url).toContain('logo.png');
  });

  it('getAppointmentTypes returns types', async () => {
    server.use(
      http.get('/api/v1/appointment-types', () =>
        HttpResponse.json([
          { id: 'at-1', name: 'Cleaning', duration: 30, color: '#000', isActive: true },
        ]),
      ),
    );
    const result = await clinicApi.getAppointmentTypes();
    expect(result.data).toHaveLength(1);
  });

  it('createAppointmentType posts a new type', async () => {
    server.use(
      http.post('/api/v1/appointment-types', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'at-2', ...body }, { status: 201 });
      }),
    );
    const result = await clinicApi.createAppointmentType({
      name: 'New',
      code: 'NEW',
      duration: 30,
      color: '#3b82f6',
      allowOnlineBooking: true,
      isActive: true,
    });
    expect(result.data?.id).toBe('at-2');
  });

  it('updateAppointmentType sends a PUT', async () => {
    server.use(
      http.put('/api/v1/appointment-types/at-1', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'at-1', name: 'X', duration: 30, isActive: true, ...body });
      }),
    );
    const result = await clinicApi.updateAppointmentType('at-1', { duration: 45 });
    expect(result.data?.duration).toBe(45);
  });

  it('deleteAppointmentType resolves', async () => {
    server.use(
      http.delete('/api/v1/appointment-types/at-1', () =>
        HttpResponse.json({ message: 'Deleted' }),
      ),
    );
    await expect(clinicApi.deleteAppointmentType('at-1')).resolves.toMatchObject({ success: true });
  });

  it('getChairs returns chairs', async () => {
    server.use(
      http.get('/api/v1/chairs', () =>
        HttpResponse.json([{ id: 'c-1', name: 'Chair 1', isActive: true }]),
      ),
    );
    const result = await clinicApi.getChairs();
    expect(result.data).toHaveLength(1);
  });

  it('createChair posts a new chair', async () => {
    server.use(
      http.post('/api/v1/chairs', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'c-2', ...body }, { status: 201 });
      }),
    );
    const result = await clinicApi.createChair({
      name: 'Chair 2',
      isActive: true,
      color: '#10b981',
    });
    expect(result.data?.id).toBe('c-2');
  });

  it('updateChair sends a PUT', async () => {
    server.use(
      http.put('/api/v1/chairs/c-1', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'c-1', name: 'Chair 1', isActive: true, ...body });
      }),
    );
    const result = await clinicApi.updateChair('c-1', { name: 'Renamed' });
    expect(result.data?.name).toBe('Renamed');
  });

  it('deleteChair resolves', async () => {
    server.use(
      http.delete('/api/v1/chairs/c-1', () =>
        HttpResponse.json({ message: 'Deleted' }),
      ),
    );
    await expect(clinicApi.deleteChair('c-1')).resolves.toMatchObject({ success: true });
  });
});
