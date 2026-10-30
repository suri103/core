import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/services/api";
import { usePaymentStats, useTransactions, useRecurringPlans, useTerminals } from "../usePayments";

vi.mock("@/services/api", () => ({
  apiClient: { get: vi.fn() },
}));

const mockedGet = vi.mocked(apiClient.get);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("usePayments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("surfaces API failure instead of returning demo statistics", async () => {
    mockedGet.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Payment service unavailable" },
    });

    const { result } = renderHook(() => usePaymentStats(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toEqual(new Error("Payment service unavailable"));
  });

  it("returns only transactions supplied by the API", async () => {
    const transaction = {
      id: "txn-1",
      patient: "Jamie Rivera",
      amount: 125,
      type: "Copay",
      method: "Card",
      status: "Completed" as const,
      date: "2026-06-20",
    };
    mockedGet.mockResolvedValue({
      success: true,
      data: { transactions: [transaction] },
    });

    const { result } = renderHook(() => useTransactions({ search: "Jamie" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data?.transactions).toEqual([transaction]);
    expect(mockedGet).toHaveBeenCalledWith("/payments/transactions", { search: "Jamie" });
  });

  it("surfaces API failure with default message when no error message is provided for stats", async () => {
    mockedGet.mockResolvedValue({
      success: false,
    });

    const { result } = renderHook(() => usePaymentStats(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(new Error("Unable to load payment statistics"));
  });

  it("loads recurring plans successfully", async () => {
    const plan = { id: "plan-1", patient: "John", plan: "Basic", amount: 50, frequency: "Monthly", nextDate: "2026-07-01", status: "Active" as const };
    mockedGet.mockResolvedValue({
      success: true,
      data: { plans: [plan] },
    });

    const { result } = renderHook(() => useRecurringPlans(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data?.plans).toEqual([plan]);
  });

  it("loads terminals successfully", async () => {
    const terminal = { id: "term-1", name: "Front Desk", status: "Online" as const, location: "Reception", lastTransaction: "2026-06-22" };
    mockedGet.mockResolvedValue({
      success: true,
      data: { terminals: [terminal] },
    });

    const { result } = renderHook(() => useTerminals(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data?.terminals).toEqual([terminal]);
  });
});