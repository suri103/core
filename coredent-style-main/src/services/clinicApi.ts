// ============================================
// CoreDent PMS - Clinic Settings API
// API service for clinic configuration
// ============================================

import { apiClient } from './api';
import type { ClinicSettings, AppointmentTypeConfig, Chair } from '@/types/clinic';
import type { ApiResponse } from '@/types/api';

export const clinicApi = {
  // Get clinic settings
  getSettings: () =>
    apiClient.get<ClinicSettings>('/settings'),

  // Update clinic settings
  updateSettings: (settings: Partial<ClinicSettings>) =>
    apiClient.put<ClinicSettings>('/settings', settings),

  // Upload clinic logo (returns URL from blob storage)
  uploadLogo: async (file: File): Promise<ApiResponse<{ url: string }>> => {
    const formData = new FormData();
    formData.append('logo', file);
    return apiClient.post<{ url: string }>('/settings/logo', formData);
  },

  // Appointment Types CRUD
  getAppointmentTypes: () =>
    apiClient.get<AppointmentTypeConfig[]>('/appointment-types'),

  createAppointmentType: (type: Omit<AppointmentTypeConfig, 'id'>) =>
    apiClient.post<AppointmentTypeConfig>('/appointment-types', type),

  updateAppointmentType: (id: string, type: Partial<AppointmentTypeConfig>) =>
    apiClient.put<AppointmentTypeConfig>(`/appointment-types/${id}`, type),

  deleteAppointmentType: (id: string) =>
    apiClient.delete<void>(`/appointment-types/${id}`),

  // Chairs/Operatories CRUD
  getChairs: () =>
    apiClient.get<Chair[]>('/chairs'),

  createChair: (chair: Omit<Chair, 'id'>) =>
    apiClient.post<Chair>('/chairs', chair),

  updateChair: (id: string, chair: Partial<Chair>) =>
    apiClient.put<Chair>(`/chairs/${id}`, chair),

  deleteChair: (id: string) =>
    apiClient.delete<void>(`/chairs/${id}`),
};
