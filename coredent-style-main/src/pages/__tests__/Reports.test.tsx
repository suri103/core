import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Reports from "../Reports";

// Mock Recharts ResponsiveContainer
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: any) => (
      <div data-testid="responsive-container" style={{ width: 800, height: 400 }}>
        {typeof children === 'function' ? children({ width: 800, height: 400 }) : children}
      </div>
    ),
  };
});

const mockMetrics = {
  appointments: {
    total: 10,
    completed: 8,
    cancelled: 1,
    noShow: 1,
    completionRate: 80,
    noShowRate: 10,
    byType: [
      { type: 'Checkup', count: 6 },
      { type: 'Cleaning', count: 4 }
    ],
    byDay: [
      { day: '2024-03-11', count: 5 },
      { day: '2024-03-12', count: 5 }
    ]
  },
  revenue: {
    totalRevenue: 5000,
    totalCollected: 4000,
    totalOutstanding: 1000,
    averagePerVisit: 500,
    byMonth: [
      { month: 'Jan', revenue: 2000, collected: 1500 },
      { month: 'Feb', revenue: 3000, collected: 2500 }
    ],
    byProcedure: [
      { procedure: 'Filling', revenue: 3000 },
      { procedure: 'Crown', revenue: 2000 }
    ]
  },
  treatmentAcceptance: {
    proposedPlans: 5,
    acceptedPlans: 4,
    completedPlans: 2,
    acceptanceRate: 80,
    completionRate: 40
  },
  chairUtilization: {
    totalChairs: 3,
    averageUtilization: 75,
    byChair: [
      { chair: 'Chair 1', utilization: 80, appointments: 15 },
      { chair: 'Chair 2', utilization: 70, appointments: 12 }
    ],
    byDayOfWeek: [
      { day: 'Mon', utilization: 75 },
      { day: 'Tue', utilization: 75 }
    ],
    peakHours: [
      { hour: '10:00 AM', utilization: 90 },
      { hour: '02:00 PM', utilization: 85 }
    ]
  }
};

const { mockGetDashboardMetrics, mockDownloadCSV } = vi.hoisted(() => ({
  mockGetDashboardMetrics: vi.fn(),
  mockDownloadCSV: vi.fn(),
}));

vi.mock('@/services/reportsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/reportsApi')>();
  return {
    reportsApi: {
      ...actual.reportsApi,
      getDashboardMetrics: mockGetDashboardMetrics,
      downloadCSV: mockDownloadCSV,
    }
  };
});

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("Reports Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetDashboardMetrics.mockResolvedValue({
      success: true,
      data: mockMetrics,
    });
  });

  it("renders the reports page and displays overview metrics", async () => {
    render(<Reports />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Total Appointments')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('$5,000')).toBeInTheDocument();
      expect(screen.getByText('80%')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  it("handles loading state", async () => {
    // Return a promise that doesn't resolve immediately
    mockGetDashboardMetrics.mockReturnValue(new Promise(() => {}));

    render(<Reports />, { wrapper: createWrapper() });

    // The screen should show skeletons or loading indicators
    // Skeletons are rendered in Reports.tsx when isLoading is true
    expect(screen.queryByText('Total Appointments')).not.toBeInTheDocument();
  });

  it("handles error state and allows retry", async () => {
    const user = userEvent.setup();
    mockGetDashboardMetrics.mockResolvedValue({
      success: false,
      error: { message: "Network Error" },
    });

    render(<Reports />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Failed to Load Reports")).toBeInTheDocument();
    });

    // Click Try Again
    const retryBtn = screen.getByRole("button", { name: /try again/i });
    mockGetDashboardMetrics.mockResolvedValue({
      success: true,
      data: mockMetrics,
    });
    await user.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText("Total Appointments")).toBeInTheDocument();
    });
  });

  it("handles empty data state", async () => {
    mockGetDashboardMetrics.mockResolvedValue({
      success: true,
      data: {
        appointments: { total: 0, completed: 0, cancelled: 0, noShow: 0, completionRate: 0, noShowRate: 0, byType: [], byDay: [] },
        revenue: { totalRevenue: 0, totalCollected: 0, totalOutstanding: 0, averagePerVisit: 0, byMonth: [], byProcedure: [] },
        treatmentAcceptance: { proposedPlans: 0, acceptedPlans: 0, completedPlans: 0, acceptanceRate: 0, completionRate: 0 },
        chairUtilization: { totalChairs: 0, averageUtilization: 0, byChair: [], byDayOfWeek: [], peakHours: [] }
      },
    });

    render(<Reports />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No Data Available")).toBeInTheDocument();
    });
  });

  it("switches tabs and exports reports", async () => {
    const user = userEvent.setup();
    render(<Reports />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Total Appointments")).toBeInTheDocument();
    });

    // 1. Appointments Tab
    const appointmentsTab = screen.getByRole("tab", { name: /appointments/i });
    await user.click(appointmentsTab);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("No-Shows")).toBeInTheDocument();

    // Click Export on Appointments Tab
    const exportBtnAppt = screen.getByRole("button", { name: /export/i });
    await user.click(exportBtnAppt);
    expect(mockDownloadCSV).toHaveBeenCalled();

    // 2. Revenue Tab
    const revenueTab = screen.getByRole("tab", { name: /revenue/i });
    await user.click(revenueTab);
    expect(screen.getByText("Total Revenue")).toBeInTheDocument();
    expect(screen.getByText("Revenue by Procedure")).toBeInTheDocument();

    // Click Export on Revenue Tab
    const exportBtnRev = screen.getByRole("button", { name: /export/i });
    await user.click(exportBtnRev);
    expect(mockDownloadCSV).toHaveBeenCalled();

    // 3. Utilization Tab
    const utilizationTab = screen.getByRole("tab", { name: /utilization/i });
    await user.click(utilizationTab);
    expect(screen.getByText("Average Utilization")).toBeInTheDocument();
    expect(screen.getByText("Total Chairs")).toBeInTheDocument();

    // Click Export on Utilization Tab
    const exportBtnUtil = screen.getByRole("button", { name: /export/i });
    await user.click(exportBtnUtil);
    expect(mockDownloadCSV).toHaveBeenCalled();
  });

  it("handles preset range changes", async () => {
    const user = userEvent.setup();
    render(<Reports />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Total Appointments")).toBeInTheDocument();
    });

    // Find the select trigger (preset range)
    // The default is "Last 30 Days"
    const presetSelect = screen.getByRole("combobox");
    await user.click(presetSelect);

    // Select "Last 7 Days"
    const option = await screen.findByText("Last 7 Days");
    await user.click(option);

    // Verify getDashboardMetrics was called again
    expect(mockGetDashboardMetrics.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
