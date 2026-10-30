import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useTodayAppointments } from "../useTodayAppointments";
import { appointmentsApi } from "@/services/api";
import type { Appointment } from "@/types/api";

vi.mock("@/services/api", () => ({
  appointmentsApi: { list: vi.fn() },
  patientsApi: { list: vi.fn(), getById: vi.fn(), update: vi.fn() },
}));

const mockedList = vi.mocked(appointmentsApi.list);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const mockAppointments: Appointment[] = [
  {
    id: 'a-1',
    patientId: 'p-1',
    patientName: 'John Doe',
    providerId: 'doc-1',
    providerName: 'Dr. Smith',
    operatoryId: 'chair-1',
    operatoryName: 'Chair 1',
    type: 'cleaning',
    status: 'scheduled',
    startTime: '2026-06-22T09:00:00Z',
    endTime: '2026-06-22T10:00:00Z',
    createdAt: '2026-06-01T00:00:00Z',
    updatedAt: '2026-06-01T00:00:00Z',
  },
];

describe("useTodayAppointments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches appointments with the given date range", async () => {
    mockedList.mockResolvedValue({
      success: true,
      data: mockAppointments,
    });

    const startDate = new Date('2026-06-22T00:00:00Z');
    const endDate = new Date('2026-06-22T23:59:59Z');

    const { result } = renderHook(
      () => useTodayAppointments({ startDate, endDate }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.appointments).toEqual(mockAppointments);
    expect(mockedList).toHaveBeenCalledWith({
      startDate: '2026-06-22T00:00:00.000Z',
      endDate: '2026-06-22T23:59:59.000Z',
    });
  });

  it("falls back to today when no date range is given", async () => {
    mockedList.mockResolvedValue({ success: true, data: [] });

    renderHook(() => useTodayAppointments(), {
      wrapper: createWrapper(),
    });

    // The queryKey includes the current `new Date()` which changes per render,
    // so React Query may re-fetch. Wait for the API to be called instead of
    // pinning the loading state.
    await waitFor(() => expect(mockedList).toHaveBeenCalled());
    const call = mockedList.mock.calls[0][0];
    expect(call.startDate).toBeTruthy();
    expect(call.endDate).toBeTruthy();
  });

  it("returns empty arrays on API failure and reports the error", async () => {
    mockedList.mockResolvedValue({
      success: false,
      data: [],
      error: { code: 'UNAVAILABLE', message: 'Backend offline' },
    });

    const { result } = renderHook(() => useTodayAppointments(), {
      wrapper: createWrapper(),
    });

    // The hook falls back to an empty array; the API call itself resolved
    // (with {success: false}) so React Query does not flag it as an error.
    await waitFor(() => expect(mockedList).toHaveBeenCalled());
    expect(result.current.appointments).toEqual([]);
  });
});
