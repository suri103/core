import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useBillingSummary } from "../useBillingSummary";
import { billingApi } from "@/services/billingApi";
import type { BillingSummary } from "@/types/billing";

vi.mock("@/services/billingApi", () => ({
  billingApi: { getSummary: vi.fn() },
}));

const mockedGetSummary = vi.mocked(billingApi.getSummary);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const mockSummary: BillingSummary = {
  totalInvoices: 5,
  totalRevenue: 15400,
  totalTax: 400,
  totalPayments: 2,
  totalCollected: 3400,
  outstandingBalance: 12000,
  statusBreakdown: [
    { status: 'pending', count: 3, amount: 3400 },
    { status: 'overdue', count: 1, amount: 1000 },
  ],
  overdueCount: 1,
  pendingCount: 3,
  pendingAmount: 3400,
};

describe("useBillingSummary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the summary and computed counts", async () => {
    mockedGetSummary.mockResolvedValue(mockSummary);

    const { result } = renderHook(() => useBillingSummary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.billingSummary).toEqual(mockSummary);
    expect(result.current.pendingCount).toBe(3);
    expect(result.current.pendingAmount).toBe(3400);
    expect(result.current.isError).toBe(false);
  });

  it("falls back to zero counts and null summary while loading", () => {
    mockedGetSummary.mockImplementation(() => new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useBillingSummary(), {
      wrapper: createWrapper(),
    });

    expect(result.current.billingSummary).toBeNull();
    expect(result.current.pendingCount).toBe(0);
    expect(result.current.pendingAmount).toBe(0);
    expect(result.current.isLoading).toBe(true);
  });

  it("surfaces an error and does not fabricate counts", async () => {
    mockedGetSummary.mockRejectedValue(new Error("Network down"));

    const { result } = renderHook(() => useBillingSummary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.billingSummary).toBeNull();
    expect(result.current.pendingCount).toBe(0);
    expect(result.current.pendingAmount).toBe(0);
    expect(result.current.error).toEqual(new Error("Network down"));
  });
});
