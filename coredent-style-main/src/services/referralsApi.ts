import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';

export interface ReferralRecord {
  id: string;
  patient_id?: string;
  patient?: { first_name?: string; last_name?: string };
  referral_type?: string;
  status?: string;
  referral_date?: string;
  referral_number?: string;
  referral_fee?: string | number;
  referral_received?: boolean;
  notes?: string;
  reason?: string;
  urgency?: string;
}

export interface ReferralSourceRecord {
  id: string;
  practice_id?: string;
  name: string;
  source_type?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  specialty?: string;
  is_active?: boolean;
  is_track_referrals?: boolean;
  notes?: string;
  total_referrals?: string;
  successful_referrals?: string;
}

type ReferralListResponse = { referrals: ReferralRecord[]; count: number };
type ReferralSourcesResponse = { sources: ReferralSourceRecord[]; count: number };

export const referralsApi = {
  list: async (params?: Record<string, unknown>): Promise<ReferralListResponse> =>
    requireApiData(await apiClient.get<ReferralListResponse>('/referrals/', params), 'Failed to load referrals'),

  listSources: async (params?: Record<string, unknown>): Promise<ReferralSourcesResponse> =>
    requireApiData(await apiClient.get<ReferralSourcesResponse>('/referrals/sources/', params), 'Failed to load referral sources'),

  create: async (data: Record<string, unknown>): Promise<ReferralRecord> =>
    requireApiData(await apiClient.post<ReferralRecord>('/referrals/', data), 'Failed to create referral'),

  update: async (id: string, data: Record<string, unknown>): Promise<ReferralRecord> =>
    requireApiData(await apiClient.put<ReferralRecord>(`/referrals/${id}`, data), 'Failed to update referral'),

  remove: async (id: string): Promise<void> =>
    requireApiSuccess(await apiClient.delete<void>(`/referrals/${id}`), 'Failed to delete referral'),

  createSource: async (data: Record<string, unknown>): Promise<ReferralSourceRecord> =>
    requireApiData(await apiClient.post<ReferralSourceRecord>('/referrals/sources/', data), 'Failed to create referral source'),

  updateSource: async (id: string, data: Record<string, unknown>): Promise<ReferralSourceRecord> =>
    requireApiData(await apiClient.put<ReferralSourceRecord>(`/referrals/sources/${id}`, data), 'Failed to update referral source'),

  removeSource: async (id: string): Promise<void> =>
    requireApiSuccess(await apiClient.delete<void>(`/referrals/sources/${id}`), 'Failed to delete referral source'),
};
