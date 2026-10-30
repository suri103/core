import { describe, it, expect, beforeEach } from 'vitest';
import { schedulingApi } from '../schedulingApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type {
  ScheduleAppointment,
  ScheduleProvider,
  PatientSearchResult,
} from '@/types/scheduling';
import type { Chair, AppointmentTypeConfig } from '@/types/clinic';

const mockAppointment: ScheduleAppointment = {
  id: 'apt-1',
  patientId: 'p-1',
  patientName: 'John Doe',
  providerId: 'doc-1',
  providerName: 'Dr. Smith',
  chairId: 'chair-1',
  chairName: 'Operatory 1',
  type: 'cleaning',
  status: 'confirmed',
  startTime: new Date('2026-06-22T09:00:00Z'),
  endTime: new Date('2026-06-22T10:00:00Z'),
  duration: 60,
};

describe('schedulingApi', () => {
  beforeEach(() => server.resetHandlers());

  it('getAppointments returns appointments in the date range', async () => {
    server.use(
      http.get('/api/v1/appointments', () =>
        HttpResponse.json({ appointments: [mockAppointment], count: 1 }),
      ),
    );
    const result = await schedulingApi.getAppointments(
      new Date('2026-06-22'),
      new Date('2026-06-22T23:59:59'),
    );
    // JSON serializes Date -> string, so compare fields explicitly
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(mockAppointment.id);
    expect(result[0].patientId).toBe(mockAppointment.patientId);
    expect(result[0].status).toBe(mockAppointment.status);
    expect(result[0].duration).toBe(mockAppointment.duration);
  });

  it('getAppointment returns a single appointment', async () => {
    server.use(
      http.get('/api/v1/appointments/apt-1', () =>
        HttpResponse.json(mockAppointment),
      ),
    );
    const result = await schedulingApi.getAppointment('apt-1');
    expect(result).not.toBeNull();
    expect(result?.id).toBe(mockAppointment.id);
    expect(result?.patientId).toBe(mockAppointment.patientId);
    expect(result?.status).toBe(mockAppointment.status);
  });

  it('createAppointment posts a new appointment', async () => {
    server.use(
      http.post('/api/v1/appointments', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockAppointment, ...body, id: 'apt-2' }, { status: 201 });
      }),
    );
    const result = await schedulingApi.createAppointment({
      patientId: 'p-1',
      patientName: 'John Doe',
      providerId: 'doc-1',
      chairId: 'chair-1',
      date: new Date('2026-06-22'),
      startTime: '09:00',
      duration: 60,
      type: 'cleaning',
      notes: 'First visit',
    });
    expect(result.id).toBe('apt-2');
  });

  it('updateAppointment sends a PUT', async () => {
    server.use(
      http.put('/api/v1/appointments/apt-1', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockAppointment, ...body });
      }),
    );
    const result = await schedulingApi.updateAppointment('apt-1', { notes: 'updated' });
    expect(result?.notes).toBe('updated');
  });

  it('updateStatus sends a PUT', async () => {
    server.use(
      http.put('/api/v1/appointments/apt-1/status', () =>
        HttpResponse.json({ message: 'updated' }),
      ),
    );
    await expect(
      schedulingApi.updateStatus('apt-1', 'confirmed'),
    ).resolves.toBeUndefined();
  });

  it('cancelAppointment posts a cancel', async () => {
    server.use(
      http.post('/api/v1/appointments/apt-1/cancel', () =>
        HttpResponse.json({ message: 'cancelled' }),
      ),
    );
    await expect(
      schedulingApi.cancelAppointment('apt-1', 'patient request'),
    ).resolves.toBeUndefined();
  });

  it('rescheduleAppointment sends a PUT with chair + time', async () => {
    server.use(
      http.put('/api/v1/appointments/apt-1/reschedule', () =>
        HttpResponse.json(mockAppointment),
      ),
    );
    const result = await schedulingApi.rescheduleAppointment(
      'apt-1',
      'chair-2',
      new Date('2026-06-23T10:00:00Z'),
    );
    expect(result).not.toBeNull();
    expect(result?.id).toBe(mockAppointment.id);
    expect(result?.patientId).toBe(mockAppointment.patientId);
  });

  it('getProviders returns provider list', async () => {
    const provider: ScheduleProvider = {
      id: 'p-1',
      name: 'Dr. Smith',
      role: 'dentist',
      color: '#000',
    };
    server.use(
      http.get('/api/v1/providers', () => HttpResponse.json([provider])),
    );
    const result = await schedulingApi.getProviders();
    expect(result).toEqual([provider]);
  });

  it('getChairs filters out inactive chairs', async () => {
    const activeChair: Chair = { id: 'c-1', name: 'Chair 1', isActive: true, color: '#000' };
    const inactiveChair: Chair = { id: 'c-2', name: 'Chair 2', isActive: false, color: '#999' };
    server.use(
      http.get('/api/v1/chairs', () =>
        HttpResponse.json([activeChair, inactiveChair]),
      ),
    );
    const result = await schedulingApi.getChairs();
    expect(result).toEqual([activeChair]);
  });

  it('getAppointmentTypes filters out inactive types', async () => {
    const active: AppointmentTypeConfig = {
      id: 't-1',
      name: 'Cleaning',
      code: 'D1110',
      duration: 30,
      color: '#000',
      isActive: true,
      allowOnlineBooking: true,
    };
    const inactive: AppointmentTypeConfig = {
      id: 't-2',
      name: 'Old',
      code: 'D0000',
      duration: 30,
      color: '#999',
      isActive: false,
      allowOnlineBooking: false,
    };
    server.use(
      http.get('/api/v1/appointment-types', () =>
        HttpResponse.json([active, inactive]),
      ),
    );
    const result = await schedulingApi.getAppointmentTypes();
    expect(result).toEqual([active]);
  });

  it('searchPatients returns results for non-empty queries', async () => {
    const results: PatientSearchResult[] = [
      { id: 'p-1', name: 'John Doe', phone: '555-1234' },
    ];
    server.use(
      http.get('/api/v1/patients/search', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('query')).toBe('John');
        return HttpResponse.json(results);
      }),
    );
    const result = await schedulingApi.searchPatients('John');
    expect(result).toEqual(results);
  });

  it('searchPatients returns [] for empty query without making a request', async () => {
    const result = await schedulingApi.searchPatients('');
    expect(result).toEqual([]);
  });
});
