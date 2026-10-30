import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAppointment,
  deleteAppointment,
  getAppointmentStats,
  listAppointments,
  listAppointmentTypes,
  sendAppointmentReminder,
  updateAppointment,
  type Appointment,
  type AppointmentListParams,
} from "@/services/appointmentsApi";
import type { ApiResponse } from "@/types/api";

interface MutationConfig {
  onSuccess?: () => void;
  onError?: () => void;
}

function requireApiSuccess<T>(response: ApiResponse<T>, action: string): T {
  if (response.success && response.data !== undefined) {
    return response.data;
  }
  throw new Error(response.error?.message || `Failed to ${action}`);
}

export function useAppointments(params?: AppointmentListParams) {
  return useQuery({
    queryKey: ["appointments", "list", params],
    queryFn: async () => {
      const response = await listAppointments(params);
      requireApiSuccess(response, "load appointments");
      return response;
    },
  });
}

export function useAppointmentStats() {
  return useQuery({
    queryKey: ["appointments", "stats"],
    queryFn: async () => {
      const response = await getAppointmentStats();
      requireApiSuccess(response, "load appointment statistics");
      return response;
    },
  });
}

export function useAppointmentTypes() {
  return useQuery({
    queryKey: ["appointments", "types"],
    queryFn: async () => {
      const response = await listAppointmentTypes();
      requireApiSuccess(response, "load appointment types");
      return response;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateAppointment(config: MutationConfig = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Omit<Appointment, "id">) =>
      requireApiSuccess(await createAppointment(data), "create appointment"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      config.onSuccess?.();
    },
    onError: () => config.onError?.(),
  });
}

export function useUpdateAppointment(config: MutationConfig = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Appointment> }) =>
      requireApiSuccess(await updateAppointment(id, data), "update appointment"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      config.onSuccess?.();
    },
    onError: () => config.onError?.(),
  });
}

export function useDeleteAppointment(config: MutationConfig = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await deleteAppointment(id);
      if (!response.success) {
        throw new Error(response.error?.message || "Failed to delete appointment");
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      config.onSuccess?.();
    },
    onError: () => config.onError?.(),
  });
}

export function useSendAppointmentReminder(config: MutationConfig = {}) {
  return useMutation({
    mutationFn: async (id: string) =>
      requireApiSuccess(await sendAppointmentReminder(id), "send appointment reminder"),
    onSuccess: () => config.onSuccess?.(),
    onError: () => config.onError?.(),
  });
}