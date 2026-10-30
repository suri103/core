import { apiClient } from './api';

/**
 * Documents / Digital Intake Forms API.
 *
 * Mirrors the backend `/api/v1/documents` endpoints. The page-level
 * counters (Templates / Pending Signatures / Signed Today) are derived
 * from these list endpoints — no hardcoded mock numbers.
 */

export type DocumentCategory =
  | 'consent'
  | 'financial'
  | 'clinical'
  | 'administrative'
  | 'policy'
  | 'marketing'
  | 'other';

export interface DocumentTemplateSummary {
  id: string;
  name: string;
  type: string;
  lastUpdated: string | null;
  usage: number;
}

export interface DocumentSummary {
  id: string;
  name: string;
  patient: string;
  type: string;
  status: 'Signed' | 'Pending Signature' | 'Draft';
  date: string | null;
}

export const documentsApi = {
  listTemplates: () => apiClient.get<DocumentTemplateSummary[]>('/documents/templates'),

  listDocuments: () => apiClient.get<DocumentSummary[]>('/documents/'),

  assignTemplate: (patientId: string, templateId: string) =>
    apiClient.post<{ status: string; id: string }>(
      `/documents/?patient_id=${encodeURIComponent(patientId)}&template_id=${encodeURIComponent(templateId)}`,
      {},
    ),
};