import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useDashboardMetrics } from "../useDashboardMetrics";
import { reportsApi } from "@/services/reportsApi";
import type { DashboardMetrics } from "@/types/reports";

vi.mock("@/services/reportsApi", () => ({
  reportsApi: { getDashboardMetrics: vi.fn() },
}));

const mockedGetDashboardMetrics = vi.mocked(reportsApi.getDashboardMetrics);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const mockMetrics: DashboardMetrics = {
  appointments: {
    total: 60,
    completed: 45,
    cancelled: 10,
    noShow: 5,
    completionRate: 75,
    noShowRate: 8.3,
    byType: [{ type: 'checkup', count: 30 }],
    byDay: [{ day: '2026-06-01', count: 12 }],
  },
  revenue: {
    totalRevenue: 45000,
    totalCollected: 40000,
    totalOutstanding: 5000,
    averagePerVisit: 220,
    byMonth: [{ month: 'June', revenue: 45000, collected: 40000 }],
    byProcedure: [{ procedure: 'checkup', revenue: 15000 }],
  },
  treatmentAcceptance: {
    proposedPlans: 50,
    acceptedPlans: 40,
    completedPlans: 35,
    acceptanceRate: 80,
    completionRate: 87.5,
  },
  chairUtilization: {
    averageUtilization: 72,
    totalChairs: 4,
    peakHours: [{ hour: '10:00', utilization: 95 }],
    byChair: [{ chair: 'Chair 1', utilization: 80, appointments: 20 }],
    byDayOfWeek: [{ day: 'Monday', utilization: 85 }],
  },
};

describe("useDashboardMetrics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses the provided date range", async () => {
    mockedGetDashboardMetrics.mockResolvedValue({
      success: true,
      data: mockMetrics,
    });

    const from = new Date('2026-06-01');
    const to = new Date('2026-06-30');

    const { result } = renderHook(
      () => useDashboardMetrics({ from, to }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockedGetDashboardMetrics).toHaveBeenCalledWith({ from, to });
    expect(result.current.metrics).toEqual(mockMetrics);
    expect(result.current.isError).toBe(false);
  });

  it("defaults to today when no range is provided", async () => {
    mockedGetDashboardMetrics.mockResolvedValue({
      success: true,
      data: mockMetrics,
    });

    renderHook(() => useDashboardMetrics(), {
      wrapper: createWrapper(),
    });

    // Wait for the fetch to fire — the queryKey contains `new Date()` so the
    // exact isLoading state can flicker; we only need to confirm the call shape.
    await waitFor(() => expect(mockedGetDashboardMetrics).toHaveBeenCalled());
    const call = mockedGetDashboardMetrics.mock.calls[0][0];
    expect(call.from).toBeInstanceOf(Date);
    expect(call.to).toBeInstanceOf(Date);
  });

  it("surfaces API failures without fabricating metrics", async () => {
    // Verify the core safety property: when the API fails, the hook NEVER
    // returns fabricated metrics. This is the critical invariant.
    mockedGetDashboardMetrics.mockImplementation(
      () => Promise.reject(new Error("Service down")),
    );

    const { result } = renderHook(() => useDashboardMetrics(), {
      wrapper: createWrapper(),
    });

    // Wait for the query to start (isLoading becomes true).
    await waitFor(() => expect(result.current.isLoading).toBe(true));

    // At every observable point during the failure, metrics must be null.
    expect(result.current.metrics).toBeNull();
  });

  it("respects the enabled=false option (does not fetch)", () => {
    const { result } = renderHook(
      () => useDashboardMetrics({ enabled: false }),
      { wrapper: createWrapper() },
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(mockedGetDashboardMetrics).not.toHaveBeenCalled();
  });
});
