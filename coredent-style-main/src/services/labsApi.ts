import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';

export interface LabCaseRecord {
  id: string;
  lab_id?: string;
  patient_id?: string;
  provider_id?: string;
  case_number?: string;
  case_type?: string;
  status?: string;
  description?: string;
  shade?: string;
  shade_notes?: string;
  teeth_involved?: string;
  sent_date?: string;
  due_date?: string;
  received_date?: string;
  delivered_date?: string;
  tracking_number?: string;
  shipping_method?: string;
  provider_notes?: string;
  lab_notes?: string;
  internal_notes?: string;
}

export interface LabVendor {
  id: string;
  practice_id?: string;
  name: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  fax?: string;
  website?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  is_active?: boolean;
  is_preferred?: boolean;
  payment_terms?: string;
  notes?: string;
}

export interface LabInvoiceRecord {
  id?: string;
  practice_id?: string;
  lab_id?: string;
  lab_case_id?: string;
  invoice_number?: string;
  invoice_date?: string;
  due_date?: string;
  status?: string;
  subtotal?: string | number;
  tax?: string | number;
  shipping?: string | number;
  discount?: string | number;
  total?: string | number;
  amount_paid?: string | number;
  notes?: string;
}

type LabCaseListResponse = { cases: LabCaseRecord[]; count: number };
type LabVendorsResponse = { labs: LabVendor[]; count: number };
type LabInvoicesResponse = { invoices: LabInvoiceRecord[]; count: number };

export const labsApi = {
  listCases: async (params?: Record<string, unknown>): Promise<LabCaseListResponse> =>
    requireApiData(await apiClient.get<LabCaseListResponse>('/labs/cases/', params), 'Failed to load lab cases'),

  listVendors: async (params?: Record<string, unknown>): Promise<LabVendorsResponse> =>
    requireApiData(await apiClient.get<LabVendorsResponse>('/labs/vendors/', params), 'Failed to load lab vendors'),

  listInvoices: async (params?: Record<string, unknown>): Promise<LabInvoicesResponse> =>
    requireApiData(await apiClient.get<LabInvoicesResponse>('/labs/invoices/', params), 'Failed to load lab invoices'),

  createCase: async (data: Record<string, unknown>): Promise<LabCaseRecord> =>
    requireApiData(await apiClient.post<LabCaseRecord>('/labs/cases/', data), 'Failed to create lab case'),

  updateCase: async (id: string, data: Record<string, unknown>): Promise<LabCaseRecord> =>
    requireApiData(await apiClient.put<LabCaseRecord>(`/labs/cases/${id}`, data), 'Failed to update lab case'),

  deleteCase: async (id: string): Promise<void> =>
    requireApiSuccess(await apiClient.delete<void>(`/labs/cases/${id}`), 'Failed to delete lab case'),

  createVendor: async (data: Record<string, unknown>): Promise<LabVendor> =>
    requireApiData(await apiClient.post<LabVendor>('/labs/vendors/', data), 'Failed to create lab'),

  updateVendor: async (id: string, data: Record<string, unknown>): Promise<LabVendor> =>
    requireApiData(await apiClient.put<LabVendor>(`/labs/vendors/${id}`, data), 'Failed to update lab'),

  deleteVendor: async (id: string): Promise<void> =>
    requireApiSuccess(await apiClient.delete<void>(`/labs/vendors/${id}`), 'Failed to delete lab'),

  createInvoice: async (data: Record<string, unknown>): Promise<LabInvoiceRecord> =>
    requireApiData(await apiClient.post<LabInvoiceRecord>('/labs/invoices/', data), 'Failed to create lab invoice'),

  payInvoice: async (
    id: string,
    data: { amount: number; transaction_id: string; payment_date?: string; notes?: string },
  ): Promise<LabInvoiceRecord> =>
    requireApiData(await apiClient.post<LabInvoiceRecord>(`/labs/invoices/${id}/pay`, data), 'Failed to record lab invoice payment'),
};
