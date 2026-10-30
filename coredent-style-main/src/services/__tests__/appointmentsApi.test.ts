import { describe, it, expect, beforeEach } from 'vitest';
import {
  listAppointments,
  getAppointment,
  createAppointment,
  updateAppointment,
  deleteAppointment,
  getAppointmentStats,
  listAppointmentTypes,
  sendAppointmentReminder,
} from '../appointmentsApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { Appointment } from '../appointmentsApi';

const wireAppointment = {
  id: 'apt-1',
  patient_id: 'p-1',
  patient_name: 'John Doe',
  provider_id: 'doc-1',
  provider_name: 'Dr. Smith',
  chair_id: 'chair-1',
  operatory_id: 'chair-1',
  operatory_name: 'Operatory 1',
  appointment_type: 'cleaning',
  type: 'cleaning',
  status: 'scheduled',
  start_time: '2026-06-22T09:00:00Z',
  end_time: '2026-06-22T10:00:00Z',
  duration: 60,
  notes: null,
  practice_id: 'x-1',
  created_at: '2026-06-22T08:00:00Z',
  updated_at: '2026-06-22T08:00:00Z',
};

describe('appointmentsApi', () => {
  beforeEach(() => server.resetHandlers());

  it('listAppointments unwraps the backend envelope and translates a day to a date range', async () => {
    server.use(
      http.get('/api/v1/appointments', ({ request }) => {
        const url = new URL(request.url);
        // The day filter must be sent as full ISO instants covering the
        // user's local day (naive strings shift the bucket by the TZ offset).
        const expectedStart = new Date(2026, 5, 22, 0, 0, 0, 0).toISOString();
        const expectedEnd = new Date(2026, 5, 22, 23, 59, 59, 999).toISOString();
        expect(url.searchParams.get('start_date')).toBe(expectedStart);
        expect(url.searchParams.get('end_date')).toBe(expectedEnd);
        return HttpResponse.json({ appointments: [wireAppointment], count: 1 });
      }),
    );
    const result = await listAppointments({ date: '2026-06-22' });
    expect(result.success).toBe(true);
    expect(result.data?.total).toBe(1);
    expect(result.data?.appointments[0].id).toBe('apt-1');
    expect(result.data?.appointments[0].patientName).toBe('John Doe');
    expect(result.data?.appointments[0].dentist).toBe('Dr. Smith');
    expect(result.data?.appointments[0].status).toBe('scheduled');
    expect(result.data?.appointments[0].type).toBe('cleaning');
    expect(result.data?.appointments[0].startTime).toBe('2026-06-22T09:00:00Z');
  });

  it('getAppointment maps a single backend appointment', async () => {
    server.use(
      http.get('/api/v1/appointments/apt-1', () => HttpResponse.json(wireAppointment)),
    );
    const result = await getAppointment('apt-1');
    expect(result.success).toBe(true);
    expect(result.data?.patientName).toBe('John Doe');
    expect(result.data?.operatoryName).toBe('Operatory 1');
    expect(result.data?.status).toBe('scheduled');
  });

  it('createAppointment resolves the patient and posts a backend payload', async () => {
    // Local wall-clock "09:00" on 2026-06-22 must convert to the matching
    // UTC instant (the same local->UTC conversion schedulingApi performs).
    const expectedStart = new Date(2026, 5, 22, 9, 0, 0, 0).toISOString();
    const expectedEnd = new Date(2026, 5, 22, 10, 0, 0, 0).toISOString();
    server.use(
      http.get('/api/v1/patients/search', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('query')).toBe('John Doe');
        return HttpResponse.json([{ id: 'p-1', name: 'John Doe', phone: '555-1234' }]);
      }),
      http.post('/api/v1/appointments', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.patient_id).toBe('p-1');
        expect(body.appointment_type).toBe('cleaning');
        expect(body.status).toBe('scheduled');
        expect(body.start_time).toBe(expectedStart);
        expect(body.end_time).toBe(expectedEnd);
        expect(body.duration).toBe(60);
        return HttpResponse.json({ ...wireAppointment, id: 'apt-2' }, { status: 201 });
      }),
    );
    const result = await createAppointment({
      patientName: 'John Doe',
      time: '09:00',
      date: '2026-06-22',
      duration: '60',
      type: 'cleaning',
      status: 'scheduled',
      dentist: '',
      patientId: '',
      providerId: '',
    } as unknown as Omit<Appointment, 'id'>);
    expect(result.success).toBe(true);
    expect(result.data?.id).toBe('apt-2');
    expect(result.data?.patientName).toBe('John Doe');
  });

  it('createAppointment returns an explicit error when the patient cannot be resolved', async () => {
    server.use(http.get('/api/v1/patients/search', () => HttpResponse.json([])));
    const result = await createAppointment({
      patientName: 'No Match',
      time: '09:00',
      type: 'cleaning',
    } as unknown as Omit<Appointment, 'id'>);
    expect(result.success).toBe(false);
    expect(result.error?.code).toBe('INVALID_PATIENT');
  });

  it('updateAppointment maps display statuses into the backend payload', async () => {
    server.use(
      http.put('/api/v1/appointments/apt-1', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.status).toBe('cancelled');
        return HttpResponse.json({ ...wireAppointment, status: 'cancelled' });
      }),
    );
    const result = await updateAppointment('apt-1', { status: 'Cancelled' } as never);
    expect(result.success).toBe(true);
    expect(result.data?.status).toBe('cancelled');
  });

  it('deleteAppointment removes an appointment', async () => {
    server.use(
      http.delete('/api/v1/appointments/apt-1', () => HttpResponse.json({ message: 'Deleted' })),
    );
    const result = await deleteAppointment('apt-1');
    expect(result.success).toBe(true);
  });

  it('getAppointmentStats returns stats', async () => {
    server.use(
      http.get('/api/v1/appointments/stats', () =>
        HttpResponse.json({ todayAppointments: 5, confirmed: 3, pending: 2, cancelled: 0, completed: 1 }),
      ),
    );
    const result = await getAppointmentStats();
    expect(result.data?.todayAppointments).toBe(5);
  });

  it('listAppointmentTypes returns types', async () => {
    server.use(
      http.get('/api/v1/appointments/types', () =>
        HttpResponse.json({ types: [{ id: 't-1', name: 'Cleaning', duration: 30 }] }),
      ),
    );
    const result = await listAppointmentTypes();
    expect(result.data?.types).toHaveLength(1);
  });

  it('sendAppointmentReminder posts the request', async () => {
    server.use(
      http.post('/api/v1/appointments/apt-1/reminder', () =>
        HttpResponse.json({ message: 'Reminder sent' }),
      ),
    );
    const result = await sendAppointmentReminder('apt-1');
    expect(result.data?.message).toBe('Reminder sent');
  });
});
