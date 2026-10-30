import { apiClient } from "./api";
import { requireApiData, requireApiSuccess } from "./apiResponse";
import type {
  PatientAttachment,
  PatientFormData,
  PatientListItem,
  PatientNote,
  PatientRecord,
  PatientSearchParams,
} from "@/types/patient";
import type { PaginatedResponse } from "@/types/api";

type RawHistoryAppointment = Record<string, unknown>;

export interface PatientAppointmentHistoryItem {
  id: string;
  patientId: string;
  patientName: string;
  providerId: string;
  providerName: string;
  chairId: string;
  chairName: string;
  appointmentTypeId: string;
  appointmentTypeName: string;
  date: string;
  startTime: string;
  endTime: string;
  status:
    | 'scheduled'
    | 'confirmed'
    | 'checked_in'
    | 'in_progress'
    | 'completed'
    | 'cancelled'
    | 'no_show';
  notes?: string;
}

const pad2 = (value: number): string => String(value).padStart(2, '0');

const formatHistoryDate = (instant: Date): string =>
  `${instant.getFullYear()}-${pad2(instant.getMonth() + 1)}-${pad2(instant.getDate())}`;

const formatHistoryTime = (instant: Date): string =>
  instant
    .toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    .replace(/\s/g, ' ')
    .toUpperCase();

const toHistoryItem = (raw: RawHistoryAppointment): PatientAppointmentHistoryItem => {
  const start = new Date(String(raw.startTime ?? ''));
  const end = new Date(String(raw.endTime ?? ''));
  const validStart = !Number.isNaN(start.getTime());
  const validEnd = !Number.isNaN(end.getTime());
  return {
    id: String(raw.id ?? ''),
    patientId: String(raw.patientId ?? ''),
    patientName: String(raw.patientName ?? ''),
    providerId: String(raw.providerId ?? ''),
    providerName: String(raw.providerName ?? ''),
    chairId: String(raw.chairId ?? raw.operatoryId ?? ''),
    chairName: raw.operatoryName ? String(raw.operatoryName) : '',
    appointmentTypeId: String(raw.appointmentTypeId ?? ''),
    appointmentTypeName: String(raw.appointmentType ?? raw.type ?? ''),
    date: validStart ? formatHistoryDate(start) : '',
    startTime: validStart ? formatHistoryTime(start) : '',
    endTime: validEnd ? formatHistoryTime(end) : '',
    status: (typeof raw.status === 'string'
      ? raw.status.toLowerCase()
      : 'scheduled') as PatientAppointmentHistoryItem['status'],
    notes: raw.notes ? String(raw.notes) : undefined,
  };
};

export const patientApi = {
  getPatients: async (
    params?: PatientSearchParams,
  ): Promise<PaginatedResponse<PatientListItem>> =>
    requireApiData(
      await apiClient.get<PaginatedResponse<PatientListItem>>(
        "/patients",
        params as unknown as Record<string, unknown>,
      ),
      "Failed to load patients",
    ),

  getPatient: async (id: string): Promise<PatientRecord | null> =>
    requireApiData(
      await apiClient.get<PatientRecord>(`/patients/${id}`),
      "Failed to load patient",
    ),

  createPatient: async (data: PatientFormData): Promise<PatientRecord> =>
    requireApiData(
      await apiClient.post<PatientRecord>("/patients", data),
      "Failed to create patient",
    ),

  updatePatient: async (
    id: string,
    data: Partial<PatientFormData>,
  ): Promise<PatientRecord | null> =>
    requireApiData(
      await apiClient.put<PatientRecord>(`/patients/${id}`, data),
      "Failed to update patient",
    ),

  updatePatientStatus: async (
    id: string,
    status: "active" | "inactive",
  ): Promise<void> => {
    requireApiSuccess(
      await apiClient.put<void>(`/patients/${id}/status`, { status }),
      "Failed to update patient status",
    );
  },

  anonymizePatient: async (id: string): Promise<PatientRecord> =>
    requireApiData(
      await apiClient.post<PatientRecord>(`/patients/${id}/anonymize`, {}),
      "Failed to anonymize patient",
    ),

  addNote: async (
    patientId: string,
    note: Omit<PatientNote, "id" | "createdAt">,
  ): Promise<PatientNote> =>
    requireApiData(
      await apiClient.post<PatientNote>(`/patients/${patientId}/notes`, note),
      "Failed to add note",
    ),

  deleteNote: async (patientId: string, noteId: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete<void>(`/patients/${patientId}/notes/${noteId}`),
      "Failed to delete note",
    );
  },

  uploadAttachment: async (
    patientId: string,
    file: File,
    category: PatientAttachment["category"],
  ): Promise<PatientAttachment> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", category);
    return requireApiData(
      await apiClient.post<PatientAttachment>(
        `/patients/${patientId}/attachments`,
        formData,
      ),
      "Failed to upload attachment",
    );
  },

  deleteAttachment: async (
    patientId: string,
    attachmentId: string,
  ): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete<void>(
        `/patients/${patientId}/attachments/${attachmentId}`,
      ),
      "Failed to delete attachment",
    );
  },

  getAppointmentHistory: async (
    patientId: string,
  ): Promise<PatientAppointmentHistoryItem[]> => {
    // The backend has no dedicated /patients/{id}/appointments route; the
    // tenant-scoped appointments list filtered by patient_id is the real
    // contract for a patient's appointment history.
    const envelope = requireApiData(
      await apiClient.get<{ appointments: RawHistoryAppointment[]; count: number }>(
        '/appointments',
        { patientId },
      ),
      'Failed to load patient appointment history',
    );
    const items = Array.isArray(envelope?.appointments) ? envelope.appointments : [];
    return items.map(toHistoryItem);
  },
};