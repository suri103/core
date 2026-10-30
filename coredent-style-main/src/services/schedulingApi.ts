/**
 * Scheduling API Service (Schedule page / useScheduling hook).
 *
 * All calls hit real backend routes (list/get/create/update/status/cancel/
 * reschedule plus the /providers, /chairs, /appointment-types and
 * /patients/search reference lookups). Responses adopt the appointment
 * envelope/field contract via the api.ts normalization boundary.
 */

import { apiClient } from "./api";
import { requireApiData, requireApiSuccess } from "./apiResponse";
import type { AppointmentTypeConfig, Chair } from "@/types/clinic";
import type {
  AppointmentFormData,
  PatientSearchResult,
  ScheduleAppointment,
  ScheduleProvider,
} from "@/types/scheduling";
import { parseTimeString } from "@/types/scheduling";

type RawAppointment = Record<string, unknown>;

const toDate = (value: unknown): Date => {
  if (value instanceof Date) return value;
  if (typeof value === "string") return new Date(value);
  return new Date(NaN);
};

const toScheduleAppointment = (raw: RawAppointment): ScheduleAppointment => ({
  id: String(raw.id ?? ""),
  patientId: String(raw.patientId ?? ""),
  patientName: String(raw.patientName ?? ""),
  patientEmail: raw.patientEmail ? String(raw.patientEmail) : undefined,
  patientPhone: raw.patientPhone ? String(raw.patientPhone) : undefined,
  providerId: String(raw.providerId ?? ""),
  providerName: String(raw.providerName ?? ""),
  chairId: String(raw.chairId ?? raw.operatoryId ?? ""),
  chairName: raw.operatoryName ? String(raw.operatoryName) : undefined,
  type: String(raw.type ?? raw.appointmentType ?? ""),
  status: (raw.status as ScheduleAppointment["status"]) ?? "scheduled",
  startTime: toDate(raw.startTime),
  endTime: toDate(raw.endTime),
  duration: typeof raw.duration === "number" ? raw.duration : Number(raw.duration) || 0,
  notes: raw.notes ? String(raw.notes) : undefined,
});

const toStartISO = (data: AppointmentFormData): string => {
  const { hours, minutes } = parseTimeString(data.startTime);
  const start = new Date(data.date);
  start.setHours(hours, minutes, 0, 0);
  return start.toISOString();
};

export const schedulingApi = {
  getAppointments: async (
    startDate: Date,
    endDate: Date,
  ): Promise<ScheduleAppointment[]> => {
    const response = await apiClient.get<{ appointments: RawAppointment[]; count: number }>(
      "/appointments",
      { startDate: startDate.toISOString(), endDate: endDate.toISOString() },
    );
    const envelope = requireApiData(response, "Failed to load appointments");
    return Array.isArray(envelope?.appointments)
      ? envelope.appointments.map(toScheduleAppointment)
      : [];
  },

  getAppointment: async (id: string): Promise<ScheduleAppointment | null> => {
    const response = await apiClient.get<RawAppointment>(`/appointments/${id}`);
    if (!response.success || !response.data) return null;
    return toScheduleAppointment(response.data);
  },

  createAppointment: async (
    data: AppointmentFormData,
  ): Promise<ScheduleAppointment> => {
    const startISO = toStartISO(data);
    const endISO = new Date(new Date(startISO).getTime() + data.duration * 60000).toISOString();
    const response = await apiClient.post<RawAppointment>("/appointments", {
      patientId: data.patientId,
      ...(data.providerId ? { providerId: data.providerId } : {}),
      ...(data.chairId ? { chairId: data.chairId } : {}),
      appointmentType: data.type || "consultation",
      status: "scheduled",
      startTime: startISO,
      endTime: endISO,
      duration: data.duration,
      ...(data.notes ? { notes: data.notes } : {}),
    });
    return toScheduleAppointment(requireApiData(response, "Failed to create appointment"));
  },

  updateAppointment: async (
    id: string,
    data: Partial<AppointmentFormData>,
  ): Promise<ScheduleAppointment> => {
    const payload: Record<string, unknown> = {};
    if (data.patientId) payload.patientId = data.patientId;
    if (data.providerId) payload.providerId = data.providerId;
    if (data.chairId) payload.chairId = data.chairId;
    if (data.type) payload.appointmentType = data.type;
    if (data.duration) payload.duration = data.duration;
    if (data.notes !== undefined) payload.notes = data.notes;
    if (data.date && data.startTime && data.duration) {
      const startISO = toStartISO(data as AppointmentFormData);
      payload.startTime = startISO;
      payload.endTime = new Date(new Date(startISO).getTime() + data.duration * 60000).toISOString();
    }
    // Throw on failure: callers previously received `null` for a failed PUT
    // and reported success anyway (silent data loss).
    const response = await apiClient.put<RawAppointment>(`/appointments/${id}`, payload);
    return toScheduleAppointment(requireApiData(response, "Failed to update appointment"));
  },

  updateStatus: async (id: string, status: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.put<void>(`/appointments/${id}/status`, { status }),
      "Failed to update appointment status",
    );
  },

  cancelAppointment: async (id: string, reason?: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.post<void>(`/appointments/${id}/cancel`, { reason }),
      "Failed to cancel appointment",
    );
  },

  rescheduleAppointment: async (
    id: string,
    newChairId: string,
    newStartTime: Date,
  ): Promise<ScheduleAppointment> => {
    const response = await apiClient.put<RawAppointment>(`/appointments/${id}/reschedule`, {
      chairId: newChairId,
      startTime: newStartTime.toISOString(),
    });
    return toScheduleAppointment(requireApiData(response, "Failed to reschedule appointment"));
  },

  getProviders: async (): Promise<ScheduleProvider[]> =>
    requireApiData(
      await apiClient.get<ScheduleProvider[]>("/providers"),
      "Failed to load providers",
    ),

  getChairs: async (): Promise<Chair[]> =>
    requireApiData(
      await apiClient.get<Chair[]>("/chairs"),
      "Failed to load chairs",
    ).filter((chair) => chair.isActive),

  getAppointmentTypes: async (): Promise<AppointmentTypeConfig[]> =>
    requireApiData(
      await apiClient.get<AppointmentTypeConfig[]>("/appointment-types"),
      "Failed to load appointment types",
    ).filter((type) => type.isActive),

  searchPatients: async (query: string): Promise<PatientSearchResult[]> => {
    if (!query.trim()) {
      return [];
    }
    return requireApiData(
      await apiClient.get<PatientSearchResult[]>("/patients/search", { query }),
      "Failed to search patients",
    );
  },
};
