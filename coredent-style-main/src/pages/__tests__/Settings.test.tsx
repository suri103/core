import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Settings from "../Settings";

// Mock Sub-tabs to easily trigger onUpdate callbacks
vi.mock('@/components/settings/GeneralSettingsTab', () => ({
  GeneralSettingsTab: ({ onUpdate }: any) => (
    <div data-testid="general-settings">
      <span>General Settings Component</span>
      <button onClick={() => onUpdate({ name: 'Updated Clinic Name' })}>Update Clinic</button>
    </div>
  ),
}));

vi.mock('@/components/settings/WorkingHoursTab', () => ({
  WorkingHoursTab: ({ onUpdate }: any) => (
    <div data-testid="working-hours">
      <span>Working Hours Component</span>
      <button onClick={() => onUpdate([])}>Update Hours</button>
    </div>
  ),
}));

vi.mock('@/components/settings/ChairsTab', () => ({
  ChairsTab: ({ onUpdate }: any) => (
    <div data-testid="chairs">
      <span>Chairs Component</span>
      <button onClick={() => onUpdate([])}>Update Chairs</button>
    </div>
  ),
}));

vi.mock('@/components/settings/AppointmentTypesTab', () => ({
  AppointmentTypesTab: ({ onUpdate }: any) => (
    <div data-testid="appointment-types">
      <span>Appointment Types Component</span>
      <button onClick={() => onUpdate([])}>Update Appointment Types</button>
    </div>
  ),
}));

vi.mock('@/components/settings/BillingPreferencesTab', () => ({
  BillingPreferencesTab: ({ onUpdate }: any) => (
    <div data-testid="billing-preferences">
      <span>Billing Preferences Component</span>
      <button onClick={() => onUpdate({ invoiceFooter: 'Updated Footer' })}>Update Billing</button>
    </div>
  ),
}));

vi.mock('@/components/settings/StaffSettingsTab', () => ({
  StaffSettingsTab: () => <div data-testid="staff-settings">Staff Settings Component</div>,
}));

vi.mock('@/components/settings/AutomationsTab', () => ({
  AutomationsTab: () => <div data-testid="automations-settings">Automations Settings Component</div>,
}));

const mockClinicSettings = {
  name: 'Test Clinic',
  workingHours: [],
  chairs: [],
  appointmentTypes: [],
};

const mockBillingPreferences = {
  invoiceFooter: 'Test Footer',
};

const { mockGetSettings, mockGetBillingPreferences } = vi.hoisted(() => ({
  mockGetSettings: vi.fn(),
  mockGetBillingPreferences: vi.fn(),
}));

vi.mock('@/services/clinicApi', () => ({
  clinicApi: {
    getSettings: mockGetSettings,
  },
}));

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>();
  return {
    ...actual,
    settingsApi: {
      ...actual.settingsApi,
      getBillingPreferences: mockGetBillingPreferences,
    },
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

describe("Settings Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSettings.mockResolvedValue({
      success: true,
      data: mockClinicSettings,
    });
    mockGetBillingPreferences.mockResolvedValue({
      success: true,
      data: mockBillingPreferences,
    });
  });

  it("renders loading state initially", async () => {
    mockGetSettings.mockReturnValue(new Promise(() => {}));
    render(<Settings />, { wrapper: createWrapper() });
    expect(screen.getByText("Loading settings...")).toBeInTheDocument();
  });

  it("renders error state when loading fails", async () => {
    mockGetSettings.mockRejectedValue(new Error("Failed to load"));
    render(<Settings />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Unable to load settings.")).toBeInTheDocument();
    });
  });

  it("loads and shows settings tabs and handles updates", async () => {
    const user = userEvent.setup();
    render(<Settings />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /clinic/i })).toBeInTheDocument();
    });

    // 1. General settings update
    expect(screen.getByTestId("general-settings")).toBeInTheDocument();
    const updateClinicBtn = screen.getByRole("button", { name: /update clinic/i });
    await user.click(updateClinicBtn);

    // 2. Working hours tab and update
    const workingHoursSubtab = screen.getByRole("tab", { name: /working hours/i });
    await user.click(workingHoursSubtab);
    expect(screen.getByTestId("working-hours")).toBeInTheDocument();
    const updateHoursBtn = screen.getByRole("button", { name: /update hours/i });
    await user.click(updateHoursBtn);

    // 3. Chairs tab and update
    const chairsSubtab = screen.getByRole("tab", { name: /chairs/i });
    await user.click(chairsSubtab);
    expect(screen.getByTestId("chairs")).toBeInTheDocument();
    const updateChairsBtn = screen.getByRole("button", { name: /update chairs/i });
    await user.click(updateChairsBtn);

    // 4. Staff Tab
    const staffTab = screen.getByRole("tab", { name: /staff/i });
    await user.click(staffTab);
    expect(screen.getByTestId("staff-settings")).toBeInTheDocument();

    // 5. Appointments Tab and update
    const apptsTab = screen.getByRole("tab", { name: /appointments/i });
    await user.click(apptsTab);
    expect(screen.getByTestId("appointment-types")).toBeInTheDocument();
    const updateApptTypesBtn = screen.getByRole("button", { name: /update appointment types/i });
    await user.click(updateApptTypesBtn);

    // 6. Billing Tab and update
    const billingTab = screen.getByRole("tab", { name: /billing/i });
    await user.click(billingTab);
    expect(screen.getByTestId("billing-preferences")).toBeInTheDocument();
    const updateBillingBtn = screen.getByRole("button", { name: /update billing/i });
    await user.click(updateBillingBtn);

    // 7. Automations Tab
    const automationsTab = screen.getByRole("tab", { name: /automations/i });
    await user.click(automationsTab);
    expect(screen.getByTestId("automations-settings")).toBeInTheDocument();
  });
});
