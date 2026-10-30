import { describe, it, expect, beforeEach } from 'vitest';
import { patientApi } from '../patientApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { PatientListItem, PatientRecord } from '@/types/patient';

const mockListItem: PatientListItem = {
  id: 'p-1',
  firstName: 'John',
  lastName: 'Doe',
  email: 'john@example.com',
  phone: '555-0100',
  dateOfBirth: '1990-01-01',
  status: 'active',
  hasMedicalAlerts: false,
  medicalAlerts: [],
  lastVisit: '2026-05-01',
  nextAppointment: '2026-07-01',
  balance: 0,
};

const mockRecord: PatientRecord = {
  id: 'p-1',
  firstName: 'John',
  lastName: 'Doe',
  email: 'john@example.com',
  phone: '555-0100',
  dateOfBirth: '1990-01-01',
  gender: 'male',
  status: 'active',
  address: { street: '1 Main', city: 'City', state: 'CA', zipCode: '94000' },
  emergencyContact: { name: 'Jane', relationship: 'spouse', phone: '555-0101' },
  medicalAlerts: [],
  medicalHistory: { conditions: [], allergies: [], medications: [], surgeries: [], familyHistory: [] },
  dentalHistory: { missingTeeth: [], hasImplants: false, hasBraces: false, hasPartialDenture: false, hasFullDenture: false, gumDiseaseHistory: false, toothSensitivity: false, grindsClenches: false },
  notes: [],
  attachments: [],
  appointmentStats: { total: 5, upcoming: 1, completed: 4, cancelled: 0, noShow: 0 },
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

describe('patientApi', () => {
  beforeEach(() => server.resetHandlers());

  describe('getPatients', () => {
    it('returns paginated list items', async () => {
      server.use(
        http.get('/api/v1/patients', () =>
          HttpResponse.json({
            data: [mockListItem],
            total: 1,
            page: 1,
            limit: 10,
            totalPages: 1,
          }),
        ),
      );
      const result = await patientApi.getPatients();
      expect(result.data).toEqual([mockListItem]);
    });

    it('passes search params', async () => {
      server.use(
        http.get('/api/v1/patients', ({ request }) => {
          const url = new URL(request.url);
          expect(url.searchParams.get('query')).toBe('John');
          return HttpResponse.json({ data: [], total: 0, page: 1, limit: 10, totalPages: 0 });
        }),
      );
      await patientApi.getPatients({ query: 'John', page: 1, limit: 10 });
    });
  });

  describe('getPatient', () => {
    it('returns a patient record', async () => {
      server.use(
        http.get('/api/v1/patients/p-1', () => HttpResponse.json(mockRecord)),
      );
      const result = await patientApi.getPatient('p-1');
      expect(result?.firstName).toBe('John');
    });

    it('throws on 404', async () => {
      server.use(
        http.get('/api/v1/patients/missing', () =>
          HttpResponse.json({ message: 'Not found' }, { status: 404 }),
        ),
      );
      await expect(patientApi.getPatient('missing')).rejects.toThrow();
    });
  });

  describe('createPatient', () => {
    it('creates a new patient', async () => {
      server.use(
        http.post('/api/v1/patients', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockRecord, ...body, id: 'p-2' }, { status: 201 });
        }),
      );
      const result = await patientApi.createPatient({
        firstName: 'Jane',
        lastName: 'Doe',
        email: 'jane@example.com',
        phone: '555-0200',
        dateOfBirth: '1992-02-02',
        gender: 'female',
        address: { street: '1 Oak', city: 'City', state: 'CA', zipCode: '94001' },
        emergencyContact: { name: 'John', relationship: 'spouse', phone: '555-0201' },
        medicalAlerts: [],
        medicalHistory: { conditions: [], allergies: [], medications: [], surgeries: [], familyHistory: [] },
        dentalHistory: { missingTeeth: [], hasImplants: false, hasBraces: false, hasPartialDenture: false, hasFullDenture: false, gumDiseaseHistory: false, toothSensitivity: false, grindsClenches: false },
      });
      expect(result.id).toBe('p-2');
    });
  });

  describe('updatePatient', () => {
    it('updates a patient', async () => {
      server.use(
        http.put('/api/v1/patients/p-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockRecord, ...body });
        }),
      );
      const result = await patientApi.updatePatient('p-1', { phone: '555-9999' });
      expect(result?.phone).toBe('555-9999');
    });
  });

  describe('updatePatientStatus', () => {
    it('sends a PUT and resolves', async () => {
      server.use(
        http.put('/api/v1/patients/p-1/status', () =>
          HttpResponse.json({ message: 'ok' }),
        ),
      );
      await expect(patientApi.updatePatientStatus('p-1', 'inactive')).resolves.toBeUndefined();
    });
  });

  describe('notes', () => {
    it('adds a note', async () => {
      server.use(
        http.post('/api/v1/patients/p-1/notes', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            { id: 'note-1', createdAt: '2026-06-22', ...body },
            { status: 201 },
          );
        }),
      );
      const result = await patientApi.addNote('p-1', {
        type: 'general',
        content: 'Patient called about pain',
        createdBy: 'staff-1',
        createdByName: 'Dr. Smith',
        isAlert: false,
        isPinned: false,
      });
      expect(result.id).toBe('note-1');
    });

    it('deletes a note', async () => {
      server.use(
        http.delete('/api/v1/patients/p-1/notes/note-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      await expect(patientApi.deleteNote('p-1', 'note-1')).resolves.toBeUndefined();
    });
  });

  describe('attachments', () => {
    it('uploads a file via FormData', async () => {
      server.use(
        http.post('/api/v1/patients/p-1/attachments', () =>
          HttpResponse.json(
            {
              id: 'att-1',
              patientId: 'p-1',
              fileName: 'xray.png',
              fileSize: 1234,
              mimeType: 'image/png',
              category: 'xray',
              uploadedAt: '2026-06-22',
              uploadedBy: 'staff-1',
            },
            { status: 201 },
          ),
        ),
      );
      const file = new File(['x'], 'xray.png', { type: 'image/png' });
      const result = await patientApi.uploadAttachment('p-1', file, 'xray');
      expect(result.id).toBe('att-1');
    });

    it('deletes an attachment', async () => {
      server.use(
        http.delete('/api/v1/patients/p-1/attachments/att-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      await expect(patientApi.deleteAttachment('p-1', 'att-1')).resolves.toBeUndefined();
    });
  });

  describe('getAppointmentHistory', () => {
    it('returns history items from the patient-filtered appointments list', async () => {
      server.use(
        http.get('/api/v1/appointments', ({ request }) => {
          const url = new URL(request.url);
          expect(url.searchParams.get('patient_id')).toBe('p-1');
          return HttpResponse.json({
            appointments: [
              {
                id: 'a-1',
                patient_id: 'p-1',
                patient_name: 'John Doe',
                provider_id: 'doc-1',
                provider_name: 'Dr. Smith',
                chair_id: 'chair-1',
                operatory_id: 'chair-1',
                operatory_name: 'Operatory 1',
                appointment_type: 'cleaning',
                type: 'cleaning',
                status: 'COMPLETED',
                start_time: '2026-05-01T14:30:00Z',
                end_time: '2026-05-01T15:00:00Z',
                duration: 30,
                notes: null,
                practice_id: 'x-1',
                created_at: '2026-05-01T14:00:00Z',
                updated_at: '2026-05-01T14:00:00Z',
              },
            ],
            count: 1,
          });
        }),
      );
      const result = await patientApi.getAppointmentHistory('p-1');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe('a-1');
      expect(result[0].providerName).toBe('Dr. Smith');
      expect(result[0].appointmentTypeName).toBe('cleaning');
      expect(result[0].status).toBe('completed');
      expect(result[0].date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(result[0].chairName).toBe('Operatory 1');
    });
  });
});
