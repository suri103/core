import type { ApiResponse } from '@/types/api';
import { apiClient } from './api';

export interface EnterprisePracticeAnalytics {
  practice_id: string;
  practice_name: string;
  production: number;
  collections: number;
  new_patients: number;
  utilization: number;
}

export interface EnterpriseGroupAnalytics {
  group_id: string;
  period: {
    start: string;
    end: string;
  };
  consolidated: {
    production: number;
    collections: number;
    new_patients: number;
    avg_utilization: number;
  };
  by_location: EnterprisePracticeAnalytics[];
}

export interface EnterprisePractice {
  id: string;
  name: string;
  address_city?: string | null;
  address_state?: string | null;
}

export interface DsoLocationPerformance {
  practice_id: string;
  practice_name: string;
  city?: string | null;
  state?: string | null;
  chair_capacity: number;
  active_providers: number;
  active_patients: number;
  production: number;
  collections: number;
  outstanding_ar: number;
}

export interface DsoProviderLeaderboardItem {
  provider_id: string;
  provider_name: string;
  role: string;
  clinic_name: string;
  completed_appointments: number;
}

export interface DsoOverview {
  group_id: string;
  total_clinics: number;
  financials: {
    total_production: number;
    total_collections: number;
    total_outstanding_ar: number;
    collection_rate: number;
  };
  ar_aging: {
    current_30: number;
    days_31_60: number;
    days_61_90: number;
    over_90: number;
  };
  locations: DsoLocationPerformance[];
  provider_leaderboard: DsoProviderLeaderboardItem[];
}

export interface DsoClinic {
  id: string;
  name: string;
  slug: string;
  phone?: string | null;
  email?: string | null;
  city?: string | null;
  state?: string | null;
  timezone?: string | null;
  chair_capacity: number;
  is_active: boolean;
}

export interface DsoPatientSearchResult {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  email?: string | null;
  phone?: string | null;
  practice_id: string;
  practice_name: string;
  practice_city?: string | null;
}

export const enterpriseApi = {
  getGroupAnalytics: (params?: { start_date?: string; end_date?: string }): Promise<ApiResponse<EnterpriseGroupAnalytics>> =>
    apiClient.get<EnterpriseGroupAnalytics>('/enterprise/group/analytics', params),

  listGroupPractices: (params?: { page?: number; limit?: number }): Promise<ApiResponse<EnterprisePractice[]>> =>
    apiClient.get<EnterprisePractice[]>('/enterprise/group/practices', params),

  getDsoOverview: (): Promise<ApiResponse<DsoOverview>> =>
    apiClient.get<DsoOverview>('/enterprise/dso/overview'),

  getDsoClinics: (): Promise<ApiResponse<DsoClinic[]>> =>
    apiClient.get<DsoClinic[]>('/enterprise/dso/clinics'),

  switchContext: (targetPracticeId: string): Promise<ApiResponse<{
    success: boolean;
    access_token: string;
    active_practice_id: string;
    active_practice_name: string;
    message: string;
  }>> =>
    apiClient.post('/enterprise/dso/switch-context', { target_practice_id: targetPracticeId }),

  searchDsoPatients: (query: string): Promise<ApiResponse<DsoPatientSearchResult[]>> =>
    apiClient.get<DsoPatientSearchResult[]>('/enterprise/dso/patients/search', { q: query }),
};
