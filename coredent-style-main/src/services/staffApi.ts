// ============================================
// CoreDent PMS - Staff Management API
// API service for staff/user management
// ============================================

import { apiClient } from './api';
import type { StaffMember, StaffInvitation, InviteStaffRequest, UpdateStaffRequest } from '@/types/staff';
import type { PaginatedResponse, ApiResponse } from '@/types/api';

export interface StaffListParams {
  search?: string;
  role?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export const staffApi = {
  // List all staff members.
  //
  // The backend returns a bare `List[UserResponse]`; the rest of the app reads a
  // `PaginatedResponse` envelope. Normalise both shapes here so either wire
  // dialect renders, and map the backend `is_active`/`last_login` fields onto the
  // frontend `status`/`lastLoginAt` contract.
  list: async (
    params?: StaffListParams,
  ): Promise<ApiResponse<PaginatedResponse<StaffMember>>> => {
    const res = await apiClient.get<PaginatedResponse<StaffMember> | StaffMember[]>(
      '/staff',
      params as unknown as Record<string, string | number>,
    );

    if (!res.success || res.data === undefined) {
      return res as ApiResponse<PaginatedResponse<StaffMember>>;
    }

    const raw = res.data;
    const isArray = Array.isArray(raw);
    const items = isArray ? (raw as StaffMember[]) : ((raw as PaginatedResponse<StaffMember>).data ?? []);
    const total = isArray ? items.length : ((raw as PaginatedResponse<StaffMember>).total ?? items.length);
    const limit = params?.limit ?? items.length;
    const page = params?.page ?? 1;

    const normalized = items.map((member) => {
      const rec = member as StaffMember & {
        isActive?: unknown;
        is_active?: unknown;
        lastLogin?: string;
        last_login?: string;
      };
      const active = rec.isActive ?? rec.is_active;
      return {
        ...member,
        status: member.status ?? (active === false ? 'inactive' : 'active'),
        lastLoginAt: member.lastLoginAt ?? rec.lastLogin ?? rec.last_login,
      };
    });

    return {
      success: true,
      data: {
        data: normalized,
        total,
        page,
        limit,
        totalPages: limit > 0 ? Math.max(1, Math.ceil(total / limit)) : 0,
      },
    };
  },

  // Get single staff member
  getById: (id: string) =>
    apiClient.get<StaffMember>(`/staff/${id}`),

  // Update staff member
  update: (id: string, data: UpdateStaffRequest) =>
    apiClient.put<StaffMember>(`/staff/${id}`, data),

  // Deactivate staff member
  deactivate: (id: string) =>
    apiClient.put<StaffMember>(`/staff/${id}/deactivate`),

  // Reactivate staff member
  reactivate: (id: string) =>
    apiClient.put<StaffMember>(`/staff/${id}/reactivate`),

  // Send staff invitation
  invite: (data: InviteStaffRequest) =>
    apiClient.post<StaffInvitation>('/staff/invitations', data),

  // List pending invitations
  listInvitations: () =>
    apiClient.get<StaffInvitation[]>('/staff/invitations'),

  // Resend invitation
  resendInvitation: (id: string) =>
    apiClient.post<StaffInvitation>(`/staff/invitations/${id}/resend`),

  // Cancel invitation
  cancelInvitation: (id: string) =>
    apiClient.delete<void>(`/staff/invitations/${id}`),
};
