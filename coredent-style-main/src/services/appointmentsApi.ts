/**
 * Appointments API Service
 * Appointment management with React Query integration.
 *
 * Adapts the backend AppointmentResponse wire contract (camelCased by the
 * api.ts boundary) into the display model the Appointments page renders:
 * translates the page's single-day `date` filter into start_date/end_date,
 * unwraps the { appointments, count } list envelope, resolves display names
 * into IDs for create/update, and normalizes statuses (UI Pending/Confirmed
 * -> backend scheduled/confirmed).
 */

import { apiClient } from './api';
import type { ApiResponse, AppointmentStatus } from '@/types/api';

// ============================================
// Types
// ============================================

export interface Appointment {
  id: string;
  patientId: string;
  patient: string;
  patientName: string;
  providerId: string;
  providerName: string;
  startTime: string;
  endTime: string;
  time: string;
  duration: string;
  type: string;
  dentist: string;
  status: AppointmentStatus;
  date?: string;
  notes?: string;
  operatoryId?: string;
  operatoryName?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface AppointmentStats {
  todayAppointments: number;
  confirmed: number;
  pending: number;
  cancelled: number;
  completed?: number;
}

export interface AppointmentType {
  id: string;
  name: string;
  duration: number;
  description?: string;
}

export interface AppointmentListParams {
  date?: string;
  startDate?: string;
  endDate?: string;
  status?: AppointmentStatus;
  search?: string;
  patientId?: string;
  providerId?: string;
}

type RawAppointment = Record<string, unknown>;

// ============================================
// Adapters
// ============================================

const STATUS_MAP: Record<string, AppointmentStatus> = {
  Confirmed: 'confirmed',
  Pending: 'scheduled',
  Cancelled: 'cancelled',
  Completed: 'completed',
  scheduled: 'scheduled',
  confirmed: 'confirmed',
  checked_in: 'checked_in',
  in_progress: 'in_progress',
  cancelled: 'cancelled',
  completed: 'completed',
  no_show: 'no_show',
};

const toStatus = (value?: unknown): AppointmentStatus => {
  const key = typeof value === 'string' ? value : '';
  return STATUS_MAP[key] ?? 'scheduled';
};

const formatTime = (iso?: unknown): string => {
  if (!iso) return '';
  const date = new Date(String(iso));
  if (Number.isNaN(date.getTime())) return '';
  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;
  return hours + ':' + minutes + ' ' + ampm;
};

const toReadModel = (raw: RawAppointment): Appointment => {
  const patientName = String(raw.patientName ?? raw.patient_name ?? '');
  const providerName = String(raw.providerName ?? raw.provider_name ?? '');
  const type = String(raw.type ?? raw.appointmentType ?? raw.appointment_type ?? '');
  const startTime = String(raw.startTime ?? raw.start_time ?? '');
  const endTime = String(raw.endTime ?? raw.end_time ?? '');
  return {
    id: String(raw.id ?? ''),
    patientId: String(raw.patientId ?? raw.patient_id ?? ''),
    patient: patientName,
    patientName,
    providerId: String(raw.providerId ?? raw.provider_id ?? ''),
    providerName,
    startTime,
    endTime,
    time: formatTime(startTime),
    duration: raw.duration != null ? String(raw.duration) : '',
    type,
    dentist: providerName,
    status: toStatus(raw.status),
    date: startTime ? startTime.slice(0, 10) : undefined,
    notes: raw.notes ? String(raw.notes) : undefined,
    operatoryId: raw.operatoryId ? String(raw.operatoryId) : undefined,
    operatoryName: raw.operatoryName ? String(raw.operatoryName) : undefined,
    createdAt: raw.createdAt ? String(raw.createdAt) : undefined,
    updatedAt: raw.updatedAt ? String(raw.updatedAt) : undefined,
  };
};


const toListQuery = (params?: AppointmentListParams): Record<string, unknown> => {
  const query: Record<string, unknown> = {};
  if (!params) return query;
  const { date, startDate, endDate, status, patientId, providerId } = params;
  if (startDate) query.startDate = startDate;
  if (endDate) query.endDate = endDate;
  if (date) {
    // Full ISO instants for the local day (start -> end). Naive strings like
    // "T00:00:00" are interpreted in the server's timezone, which shifts the
    // bucket to the wrong day for non-UTC browsers.
    const [year, month, day] = date.slice(0, 10).split('-').map((part) => parseInt(part, 10));
    const startOfDay = new Date(year, (month || 1) - 1, day || 1);
    startOfDay.setHours(0, 0, 0, 0);
    const endOfDay = new Date(startOfDay);
    endOfDay.setHours(23, 59, 59, 999);
    query.startDate = startOfDay.toISOString();
    query.endDate = endOfDay.toISOString();
  }
  if (status) query.status = toStatus(status);
  if (patientId) query.patientId = patientId;
  if (providerId) query.providerId = providerId;
  return query;
};

const resolvePatientId = async (name?: string, id?: string): Promise<string | null> => {
  if (id) return id;
  if (!name || !name.trim()) return null;
  const response = await apiClient.get<Array<{ id?: unknown; name?: unknown }>>('/patients/search', {
    query: name.trim(),
  });
  const list = Array.isArray(response.data) ? response.data : [];
  if (list.length === 0) return null;
  // Shared names are common in a practice; never silently book "first match".
  // Prefer an exact full-name match, otherwise only accept an unambiguous
  // single result.
  const needle = name.trim().toLowerCase();
  const exactMatches = list.filter(
    (candidate) => String(candidate.name ?? '').trim().toLowerCase() === needle,
  );
  if (exactMatches.length === 1) return String(exactMatches[0]?.id ?? '');
  if (exactMatches.length > 1) return null;
  if (list.length === 1) return String(list[0]?.id ?? '');
  return null;
};

const resolveProviderId = async (dentist?: string, id?: string): Promise<string | null> => {
  if (id) return id;
  if (!dentist || !dentist.trim()) return null;
  const response = await apiClient.get<Array<{ id?: unknown; name?: unknown }>>('/providers');
  const providers = Array.isArray(response.data) ? response.data : [];
  const needle = dentist.trim().toLowerCase();
  const match = providers.find(
    (provider) =>
      String(provider.name ?? '').toLowerCase().includes(needle) ||
      needle.includes(String(provider.name ?? '').toLowerCase()),
  );
  return match ? String(match.id ?? '') : null;
};

const parseClock = (time: string): { hours: number; minutes: number } => {
  const clean = time.trim();
  const ampm = clean.match(/^(1[0-2]|0?[1-9]):([0-5][0-9])\s*(AM|PM)$/i);
  if (ampm) {
    let hours = parseInt(ampm[1], 10);
    const minutes = parseInt(ampm[2], 10);
    if (ampm[3].toUpperCase() === 'PM' && hours < 12) hours += 12;
    if (ampm[3].toUpperCase() === 'AM' && hours === 12) hours = 0;
    return { hours, minutes };
  }
  const parts = clean.split(':');
  return { hours: parseInt(parts[0], 10) || 0, minutes: parseInt(parts[1], 10) || 0 };
};

const buildTimes = (data: Partial<Appointment>): { startTime: string; endTime: string; duration: number } => {
  const day = (data.date || new Date().toISOString().slice(0, 10)).slice(0, 10);
  const { hours, minutes } = parseClock(data.time || '09:00');
  // Build the instant from the local wall-clock digits (same pattern as
  // schedulingApi.toStartISO). Date.UTC previously treated "9:00 AM" as
  // 9:00 UTC, storing shifted times for every non-UTC browser.
  const start = new Date(
    parseInt(day.slice(0, 4), 10),
    parseInt(day.slice(5, 7), 10) - 1,
    parseInt(day.slice(8, 10), 10),
    hours,
    minutes,
    0,
    0,
  );
  const duration = Math.max(1, parseInt(String(data.duration).replace(/\D/g, ''), 10) || 30);
  const end = new Date(start.getTime() + duration * 60000);
  return { startTime: start.toISOString(), endTime: end.toISOString(), duration };
};


// ============================================
// API Functions
// ============================================

export const listAppointments = async (
  params?: AppointmentListParams,
): Promise<ApiResponse<{ appointments: Appointment[]; total: number }>> => {
  const response = await apiClient.get<{ appointments: RawAppointment[]; count: number }>(
    '/appointments',
    toListQuery(params),
  );
  if (response.success && response.data && Array.isArray(response.data.appointments)) {
    const appointments = response.data.appointments.map(toReadModel);
    const total =
      typeof response.data.count === 'number' ? response.data.count : appointments.length;
    return { ...response, data: { appointments, total } };
  }
  return { ...response, data: { appointments: [], total: 0 } };
};

export const getAppointment = async (id: string): Promise<ApiResponse<Appointment>> => {
  const response = await apiClient.get<RawAppointment>(`/appointments/${id}`);
  if (response.success && response.data) {
    return { ...response, data: toReadModel(response.data) };
  }
  return { ...response, data: undefined as unknown as Appointment };
};

export const createAppointment = async (
  data: Omit<Appointment, 'id'>,
): Promise<ApiResponse<Appointment>> => {
  const patientId = await resolvePatientId(data.patientName || data.patient, data.patientId);
  if (!patientId) {
    return {
      success: false,
      error: {
        code: 'INVALID_PATIENT',
        message: 'Could not resolve the patient. Enter a valid Patient ID or pick an existing patient.',
      },
    };
  }
  const providerId = await resolveProviderId(data.dentist, data.providerId);
  const times = buildTimes(data);
  const response = await apiClient.post<RawAppointment>('/appointments', {
    patientId,
    ...(providerId ? { providerId } : {}),
    ...(data.operatoryId ? { chairId: data.operatoryId } : {}),
    appointmentType: data.type || 'consultation',
    status: toStatus(data.status),
    startTime: times.startTime,
    endTime: times.endTime,
    duration: times.duration,
    ...(data.notes ? { notes: data.notes } : {}),
  });
  if (response.success && response.data) {
    return { ...response, data: toReadModel(response.data) };
  }
  return { ...response, data: undefined as unknown as Appointment };
};

export const updateAppointment = async (
  id: string,
  data: Partial<Appointment>,
): Promise<ApiResponse<Appointment>> => {
  const payload: Record<string, unknown> = {};
  if (data.patientName || data.patient) {
    const patientId = await resolvePatientId(data.patientName || data.patient, data.patientId);
    if (patientId) payload.patientId = patientId;
  }
  if (data.dentist) {
    const providerId = await resolveProviderId(data.dentist, data.providerId);
    if (providerId) payload.providerId = providerId;
  }
  if (data.operatoryId) payload.chairId = data.operatoryId;
  if (data.type) payload.appointmentType = data.type;
  if (data.status) payload.status = toStatus(data.status);
  if (data.time) {
    const times = buildTimes(data);
    payload.startTime = times.startTime;
    payload.endTime = times.endTime;
    payload.duration = times.duration;
  } else if (data.duration) {
    payload.duration = Math.max(1, parseInt(String(data.duration).replace(/\D/g, ''), 10) || 30);
  }
  if (data.notes) payload.notes = data.notes;
  const response = await apiClient.put<RawAppointment>(`/appointments/${id}`, payload);
  if (response.success && response.data) {
    return { ...response, data: toReadModel(response.data) };
  }
  return { ...response, data: undefined as unknown as Appointment };
};

export const deleteAppointment = async (id: string): Promise<ApiResponse<void>> => {
  return apiClient.delete<void>(`/appointments/${id}`);
};

export const getAppointmentStats = async (): Promise<ApiResponse<AppointmentStats>> => {
  return apiClient.get<AppointmentStats>('/appointments/stats');
};

export const listAppointmentTypes = async (): Promise<ApiResponse<{ types: AppointmentType[] }>> => {
  return apiClient.get<{ types: AppointmentType[] }>('/appointments/types');
};

export const sendAppointmentReminder = async (
  id: string,
): Promise<ApiResponse<{ message: string }>> => {
  return apiClient.post<{ message: string }>(`/appointments/${id}/reminder`, {});
};
