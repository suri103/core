import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import ClinicSettings from "../admin/ClinicSettings";

// Mock sub-tabs
vi.mock('@/components/settings/GeneralSettingsTab', () => ({
  GeneralSettingsTab: ({ onUpdate }: any) => (
    <div data-testid="general-tab">
      <button onClick={() => onUpdate({ name: 'New Clinic Name' })}>Update Name</button>
    </div>
  ),
}));

vi.mock('@/components/settings/WorkingHoursTab', () => ({
  WorkingHoursTab: ({ onUpdate }: any) => (
    <div data-testid="hours-tab">
      <button onClick={() => onUpdate([])}>Update Hours</button>
    </div>
  ),
}));

vi.mock('@/components/settings/ChairsTab', () => ({
  ChairsTab: ({ onUpdate }: any) => (
    <div data-testid="chairs-tab">
      <button onClick={() => onUpdate([])}>Update Chairs</button>
    </div>
  ),
}));

vi.mock('@/components/settings/AppointmentTypesTab', () => ({
  AppointmentTypesTab: ({ onUpdate }: any) => (
    <div data-testid="appointments-tab">
      <button onClick={() => onUpdate([])}>Update Appointments</button>
    </div>
  ),
}));

// Mock Toast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

// Mock clinicApi
const { mockGetSettings } = vi.hoisted(() => ({
  mockGetSettings: vi.fn(),
}));

vi.mock('@/services/clinicApi', () => ({
  clinicApi: {
    getSettings: mockGetSettings,
  },
}));

const mockClinicSettings = {
  name: 'CoreDent Clinic',
  email: 'info@coredent.com',
  phone: '123-456-7890',
  address: '123 Main St',
  workingHours: [],
  chairs: [],
  appointmentTypes: [],
};

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("ClinicSettings Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockGetSettings.mockReturnValue(new Promise(() => {})); // never resolves
    render(<ClinicSettings />, { wrapper: createWrapper() });
    expect(screen.getByText(/loading clinic settings/i)).toBeInTheDocument();
  });

  it("renders error state when loading fails", async () => {
    mockGetSettings.mockRejectedValue(new Error("Network Error"));
    render(<ClinicSettings />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/unable to load clinic settings/i)).toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Error',
      variant: 'destructive',
    }));
  });

  it("loads and shows settings tabs and handles updates", async () => {
    const user = userEvent.setup();
    mockGetSettings.mockResolvedValue({
      success: true,
      data: mockClinicSettings,
    });

    render(<ClinicSettings />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Configure your practice settings, working hours, and appointment types")).toBeInTheDocument();
    });

    // Verify general tab is shown by default
    expect(screen.getByTestId("general-tab")).toBeInTheDocument();

    // Trigger general update
    await user.click(screen.getByRole("button", { name: /update name/i }));

    // Switch to Hours tab
    await user.click(screen.getByRole("tab", { name: /hours/i }));
    expect(screen.getByTestId("hours-tab")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /update hours/i }));

    // Switch to Chairs tab
    await user.click(screen.getByRole("tab", { name: /chairs/i }));
    expect(screen.getByTestId("chairs-tab")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /update chairs/i }));

    // Switch to Appointments tab
    await user.click(screen.getByRole("tab", { name: /appointments/i }));
    expect(screen.getByTestId("appointments-tab")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /update appointments/i }));
  });
});
