import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Payments from "../Payments";
import {
  usePaymentStats,
  useRecurringPlans,
  useTerminals,
  useTransactions,
} from "@/hooks/usePayments";

vi.mock("@/hooks/usePayments", () => ({
  usePaymentStats: vi.fn(),
  useTransactions: vi.fn(),
  useRecurringPlans: vi.fn(),
  useTerminals: vi.fn(),
}));

// Payments formats money via useCurrencyFormatter, which reads the auth user.
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ user: null }),
}));

const mockedStats = vi.mocked(usePaymentStats);
const mockedTransactions = vi.mocked(useTransactions);
const mockedRecurring = vi.mocked(useRecurringPlans);
const mockedTerminals = vi.mocked(useTerminals);

function queryResult(data: unknown, overrides: Record<string, unknown> = {}) {
  return {
    data,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as never;
}

describe("Payments", () => {
  beforeEach(() => {
    mockedStats.mockReturnValue(queryResult({
      success: true,
      data: {
        todayRevenue: 1250,
        todayTransactions: 4,
        monthRevenue: 9200,
        monthGrowth: 5,
        pendingPayments: 300,
        pendingCount: 2,
        recurringRevenue: 1800,
      },
    }));
    mockedTransactions.mockReturnValue(queryResult({
      success: true,
      data: {
        transactions: [{
          id: "txn-1",
          patient: "Jamie Rivera",
          amount: 125,
          type: "Copay",
          method: "Card",
          status: "Completed",
          date: "2026-06-20",
        }],
      },
    }));
    mockedRecurring.mockReturnValue(queryResult({ success: true, data: { plans: [] } }));
    mockedTerminals.mockReturnValue(queryResult({ success: true, data: { terminals: [] } }));
  });

  it("renders provider-confirmed payment data", () => {
    render(<Payments />);

    expect(screen.getByRole("heading", { name: "Payments" })).toBeInTheDocument();
    expect(screen.getByText("$1,250.00")).toBeInTheDocument();
    expect(screen.getByText("4 transactions")).toBeInTheDocument();
    expect(screen.getByText("Jamie Rivera")).toBeInTheDocument();
  });

  it("shows an explicit failure state instead of demo financial data", () => {
    mockedStats.mockReturnValue(queryResult(undefined, { isError: true, error: new Error("offline") }));
    mockedTransactions.mockReturnValue(queryResult(undefined, { isError: true, error: new Error("offline") }));

    render(<Payments />);

    expect(screen.getByRole("alert")).toHaveTextContent("Payment data is currently unavailable");
    expect(screen.queryByText("Sarah Jenkins")).not.toBeInTheDocument();
    expect(screen.queryByText("$48,900.00")).not.toBeInTheDocument();
  });

  it("does not expose unsupported UPI or raw card collection", () => {
    render(<Payments />);

    expect(screen.getByRole("button", { name: "UPI unavailable" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Process Payment" }));

    expect(screen.getByRole("dialog")).toHaveTextContent("Credit card payments unavailable");
    expect(screen.getByRole("dialog")).toHaveTextContent("No card number or CVV is collected");
    expect(screen.queryByLabelText(/card number/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/cvv/i)).not.toBeInTheDocument();
  });
});