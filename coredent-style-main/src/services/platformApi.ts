/**
 * Platform (Super Admin) API client
 *
 * Cross-tenant SaaS-ops endpoints under /platform/*. Every call requires the
 * SUPER_ADMIN role server-side; the frontend gates the console routes too.
 */
import { apiClient } from './api';
import type { ApiResponse } from '@/types/api';
import { requireApiData } from './apiResponse';

export interface PlatformMetrics {
  total_clinics: number;
  active_clinics: number;
  suspended_clinics: number;
  total_users: number;
  active_users: number;
  active_subscriptions: number;
  trialing_subscriptions: number;
  past_due_subscriptions: number;
  failed_payment_clinics: number;
  mrr: number | string;
  churn_rate_percent: number;
  new_registrations_this_month: number;
  canceled_this_month: number;
}

export interface PlatformClinic {
  id: string;
  name: string;
  public_slug: string;
  email: string | null;
  is_active: boolean;
  country: string | null;
  timezone: string | null;
  currency: string | null;
  user_count: number;
  patient_count: number;
  created_at: string;
}

export interface PlatformClinicDetail {
  clinic: {
    id: string;
    name: string;
    public_slug: string;
    email: string | null;
    phone: string | null;
    is_active: boolean;
    country: string | null;
    timezone: string | null;
    currency: string | null;
    created_at: string;
  };
  users: Array<{
    id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
    last_login: string | null;
    is_email_verified: boolean;
  }>;
  subscription: {
    id: string;
    status: string;
    plan_name: string | null;
    plan_amount: number | null;
    current_period_end: string | null;
    trial_end: string | null;
  } | null;
  patient_count: number;
}

export interface PlatformUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  practice_id: string;
  practice_name: string | null;
  is_active: boolean;
  is_email_verified: boolean;
  last_login: string | null;
  created_at: string;
}

export interface PlatformSubscription {
  id: string;
  practice_id: string;
  status: string;
  plan_name: string | null;
  plan_amount: number | null;
  interval: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  canceled_at: string | null;
}

export interface PlatformAuditEvent {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  user_id: string | null;
  actor_email: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface PlatformPage {
  total: number;
  limit: number;
  offset: number;
}


export const platformApi = {
  async getMetrics(): Promise<ApiResponse<PlatformMetrics>> {
    return apiClient.get<PlatformMetrics>('/platform/metrics');
  },

  async listClinics(params?: {
    search?: string;
    status_filter?: 'active' | 'suspended';
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PlatformPage & { clinics: PlatformClinic[] }>> {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.status_filter) query.set('status_filter', params.status_filter);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    const qs = query.toString();
    return apiClient.get<PlatformPage & { clinics: PlatformClinic[] }>(
      `/platform/clinics${qs ? `?${qs}` : ''}`,
    );
  },

  async getClinic(clinicId: string): Promise<ApiResponse<PlatformClinicDetail>> {
    return apiClient.get<PlatformClinicDetail>(`/platform/clinics/${clinicId}`);
  },

  async suspendClinic(
    clinicId: string,
    reason?: string,
  ): Promise<ApiResponse<{ is_active: boolean }>> {
    return apiClient.put<{ is_active: boolean }>(
      `/platform/clinics/${clinicId}/suspend`,
      { reason },
    );
  },

  async reactivateClinic(clinicId: string): Promise<ApiResponse<{ is_active: boolean }>> {
    return apiClient.put<{ is_active: boolean }>(
      `/platform/clinics/${clinicId}/reactivate`,
      {},
    );
  },

  async listUsers(params?: {
    search?: string;
    role?: string;
    clinic_id?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PlatformPage & { users: PlatformUser[] }>> {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.role) query.set('role', params.role);
    if (params?.clinic_id) query.set('clinic_id', params.clinic_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    const qs = query.toString();
    return apiClient.get<PlatformPage & { users: PlatformUser[] }>(
      `/platform/users${qs ? `?${qs}` : ''}`,
    );
  },

  async listSubscriptions(params?: {
    status_filter?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PlatformPage & { subscriptions: PlatformSubscription[] }>> {
    const query = new URLSearchParams();
    if (params?.status_filter) query.set('status_filter', params.status_filter);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    const qs = query.toString();
    return apiClient.get<PlatformPage & { subscriptions: PlatformSubscription[] }>(
      `/platform/subscriptions${qs ? `?${qs}` : ''}`,
    );
  },

  async listAuditEvents(params?: {
    action_contains?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PlatformPage & { events: PlatformAuditEvent[] }>> {
    const query = new URLSearchParams();
    if (params?.action_contains) query.set('action_contains', params.action_contains);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    const qs = query.toString();
    return apiClient.get<PlatformPage & { events: PlatformAuditEvent[] }>(
      `/platform/audit-events${qs ? `?${qs}` : ''}`,
    );
  },

  async deactivateUser(
    userId: string,
    reason?: string,
  ): Promise<ApiResponse<{ is_active: boolean; email: string }>> {
    return apiClient.put<{ is_active: boolean; email: string }>(
      `/platform/users/${userId}/deactivate`,
      { reason },
    );
  },

  async reactivateUser(
    userId: string,
  ): Promise<ApiResponse<{ is_active: boolean; email: string }>> {
    return apiClient.put<{ is_active: boolean; email: string }>(
      `/platform/users/${userId}/reactivate`,
      {},
    );
  },
};

// Unwrapped variants for one-shot calls (mutations) where a caller wants
// data directly instead of the ApiResponse envelope.
export async function suspendClinicNow(
  clinicId: string,
  reason?: string,
): Promise<{ is_active: boolean }> {
  return requireApiData(
    await platformApi.suspendClinic(clinicId, reason),
    'Failed to suspend clinic',
  );
}

export async function reactivateClinicNow(
  clinicId: string,
): Promise<{ is_active: boolean }> {
  return requireApiData(
    await platformApi.reactivateClinic(clinicId),
    'Failed to reactivate clinic',
  );
}

export async function deactivateUserNow(
  userId: string,
  reason?: string,
): Promise<{ is_active: boolean; email: string }> {
  return requireApiData(
    await platformApi.deactivateUser(userId, reason),
    'Failed to deactivate user',
  );
}

export async function reactivateUserNow(
  userId: string,
): Promise<{ is_active: boolean; email: string }> {
  return requireApiData(
    await platformApi.reactivateUser(userId),
    'Failed to reactivate user',
  );
}
