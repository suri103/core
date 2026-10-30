import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAppointment,
  listAppointments,
  deleteAppointment,
  getAppointmentStats,
  listAppointmentTypes,
  sendAppointmentReminder,
  updateAppointment,
} from "@/services/appointmentsApi";
import {
  useAppointments,
  useCreateAppointment,
  useAppointmentStats,
  useAppointmentTypes,
  useUpdateAppointment,
  useDeleteAppointment,
  useSendAppointmentReminder,
} from "../useAppointments";

vi.mock("@/services/appointmentsApi", () => ({
  createAppointment: vi.fn(),
  deleteAppointment: vi.fn(),
  getAppointmentStats: vi.fn(),
  listAppointments: vi.fn(),
  listAppointmentTypes: vi.fn(),
  sendAppointmentReminder: vi.fn(),
  updateAppointment: vi.fn(),
}));

const mockedCreateAppointment = vi.mocked(createAppointment);
const mockedListAppointments = vi.mocked(listAppointments);
const mockedDeleteAppointment = vi.mocked(deleteAppointment);
const mockedGetAppointmentStats = vi.mocked(getAppointmentStats);
const mockedListAppointmentTypes = vi.mocked(listAppointmentTypes);
const mockedSendAppointmentReminder = vi.mocked(sendAppointmentReminder);
const mockedUpdateAppointment = vi.mocked(updateAppointment);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useAppointments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("surfaces API failure instead of returning fabricated appointments", async () => {
    mockedListAppointments.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Scheduling service unavailable" },
    });

    const { result } = renderHook(
      () => useAppointments({ date: "2026-06-21" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toEqual(new Error("Scheduling service unavailable"));
  });

  it("surfaces API failure with default message when no error message is provided", async () => {
    mockedListAppointments.mockResolvedValue({
      success: false,
    });

    const { result } = renderHook(
      () => useAppointments({ date: "2026-06-21" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(new Error("Failed to load appointments"));
  });

  it("loads appointment stats successfully", async () => {
    const stats = { todayAppointments: 5, confirmed: 3, pending: 2, cancelled: 0 };
    mockedGetAppointmentStats.mockResolvedValue({ success: true, data: stats });

    const { result } = renderHook(() => useAppointmentStats(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ success: true, data: stats });
  });

  it("loads appointment types successfully", async () => {
    const types = { types: [{ id: "t1", name: "Checkup", duration: 30 }] as any };
    mockedListAppointmentTypes.mockResolvedValue({ success: true, data: types });

    const { result } = renderHook(() => useAppointmentTypes(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ success: true, data: types });
  });

  it("creates appointments through the API and invokes the success callback", async () => {
    const appointment = {
      patient: "patient-1",
      patientName: "Jamie Rivera",
      patientId: "patient-1",
      providerId: "doc-1",
      providerName: "Dr. Chen",
      time: "10:00 AM",
      duration: "30",
      type: "Exam",
      dentist: "Dr. Chen",
      status: "scheduled" as const,
      startTime: "2026-06-22T10:00:00Z",
      endTime: "2026-06-22T10:30:00Z",
      date: "2026-06-22",
    };
    mockedCreateAppointment.mockResolvedValue({
      success: true,
      data: { id: "appointment-1", ...appointment },
    });
    const onSuccess = vi.fn();

    const { result } = renderHook(
      () => useCreateAppointment({ onSuccess }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutateAsync(appointment);
    });

    expect(mockedCreateAppointment).toHaveBeenCalledWith(appointment);
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("invokes onError callback on creation failure", async () => {
    mockedCreateAppointment.mockResolvedValue({ success: false, error: { message: "Creation error", code: "ERR" } });
    const onError = vi.fn();
    const { result } = renderHook(() => useCreateAppointment({ onError }), { wrapper: createWrapper() });

    await act(async () => {
      await expect(result.current.mutateAsync({} as any)).rejects.toThrow("Creation error");
    });
    expect(onError).toHaveBeenCalledOnce();
  });

  it("updates appointments and invalidates queries on success", async () => {
    mockedUpdateAppointment.mockResolvedValue({ success: true, data: { id: "1", status: "Confirmed" } as any });
    const onSuccess = vi.fn();

    const { result } = renderHook(() => useUpdateAppointment({ onSuccess }), { wrapper: createWrapper() });
    await act(async () => {
      await result.current.mutateAsync({ id: "1", data: { status: "confirmed" } });
    });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("invokes onError callback on update failure", async () => {
    mockedUpdateAppointment.mockResolvedValue({ success: false, error: { message: "Update error", code: "ERR" } });
    const onError = vi.fn();

    const { result } = renderHook(() => useUpdateAppointment({ onError }), { wrapper: createWrapper() });
    await act(async () => {
      await expect(result.current.mutateAsync({ id: "1", data: {} })).rejects.toThrow("Update error");
    });
    expect(onError).toHaveBeenCalledOnce();
  });

  it("deletes appointments and invalidates queries on success", async () => {
    mockedDeleteAppointment.mockResolvedValue({ success: true, data: undefined });
    const onSuccess = vi.fn();

    const { result } = renderHook(() => useDeleteAppointment({ onSuccess }), { wrapper: createWrapper() });
    await act(async () => {
      await result.current.mutateAsync("1");
    });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("throws default error on delete failure with no message, and calls onError", async () => {
    mockedDeleteAppointment.mockResolvedValue({ success: false });
    const onError = vi.fn();

    const { result } = renderHook(() => useDeleteAppointment({ onError }), { wrapper: createWrapper() });
    await act(async () => {
      await expect(result.current.mutateAsync("1")).rejects.toThrow("Failed to delete appointment");
    });
    expect(onError).toHaveBeenCalledOnce();
  });

  it("sends reminder successfully", async () => {
    mockedSendAppointmentReminder.mockResolvedValue({ success: true, data: { message: "Sent" } });
    const onSuccess = vi.fn();

    const { result } = renderHook(() => useSendAppointmentReminder({ onSuccess }), { wrapper: createWrapper() });
    await act(async () => {
      await result.current.mutateAsync("1");
    });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("invokes onError callback on reminder failure", async () => {
    mockedSendAppointmentReminder.mockResolvedValue({ success: false, error: { message: "Reminder error", code: "ERR" } });
    const onError = vi.fn();

    const { result } = renderHook(() => useSendAppointmentReminder({ onError }), { wrapper: createWrapper() });
    await act(async () => {
      await expect(result.current.mutateAsync("1")).rejects.toThrow("Reminder error");
    });
    expect(onError).toHaveBeenCalledOnce();
  });
});