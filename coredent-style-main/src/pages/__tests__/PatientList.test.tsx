import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import PatientList from "../patients/PatientList";

// Mock Navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock Virtualizer
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: vi.fn().mockImplementation(({ count }) => ({
    getTotalSize: () => count * 72,
    getVirtualItems: () => Array.from({ length: count }).map((_, index) => ({
      index,
      start: index * 72,
      size: 72,
    })),
    measureElement: vi.fn(),
  })),
}));

// Mock DropdownMenu to render inline to avoid Radix issues in JSDOM
vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: any) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: any) => (
    <button onClick={onClick}>{children}</button>
  ),
  DropdownMenuSeparator: () => <div />,
}));

// Mock PatientDialog
vi.mock('@/components/patients/PatientDialog', () => ({
  PatientDialog: ({ open, onSave }: any) => (
    open ? (
      <div data-testid="patient-dialog">
        <button onClick={onSave}>Save Patient</button>
      </div>
    ) : null
  ),
}));

// Mock Select to render as standard HTML select to avoid Radix portal/trigger issues in JSDOM
vi.mock('@/components/ui/select', () => ({
  Select: ({ children, value, onValueChange }: any) => (
    <select value={value} onChange={(e) => onValueChange(e.target.value)}>
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: any) => <div>{children}</div>,
  SelectValue: ({ placeholder }: any) => <span>{placeholder}</span>,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ children, value }: any) => <option value={value}>{children}</option>,
}));

// Mock Toast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

// The list reads the practice country (for the create dialog) from auth
vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ user: null }),
}));

// Mock patientApi
const { mockGetPatients } = vi.hoisted(() => ({
  mockGetPatients: vi.fn(),
}));

vi.mock('@/services/patientApi', () => ({
  patientApi: {
    getPatients: mockGetPatients,
  },
}));

const mockPatients = [
  { id: '1', firstName: 'John', lastName: 'Doe', phone: '123-456-7890', email: 'john@example.com', dateOfBirth: '1990-01-01', lastVisit: '2026-05-01', nextAppointment: '2026-07-01', status: 'active', hasMedicalAlerts: true, medicalAlerts: ['Penicillin Allergy'] },
  { id: '2', firstName: 'Jane', lastName: 'Smith', phone: '987-654-3210', email: 'jane@example.com', dateOfBirth: '1985-05-15', lastVisit: null, nextAppointment: null, status: 'inactive', hasMedicalAlerts: false, medicalAlerts: [] },
];

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

describe("PatientList Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPatients.mockResolvedValue({
      data: mockPatients,
      total: 2,
    });
  });

  it("renders patient directory and loads initial list", async () => {
    render(<PatientList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/2 patients in directory/i)).toBeInTheDocument();
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });
  });

  it("handles loading error gracefully", async () => {
    mockGetPatients.mockRejectedValueOnce(new Error("API Error"));
    render(<PatientList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Error',
        variant: 'destructive',
      }));
    });
  });

  it("filters patient list by search query", async () => {
    const user = userEvent.setup();
    render(<PatientList />, { wrapper: createWrapper() });

    const searchInput = screen.getByPlaceholderText(/search by name/i);
    await user.type(searchInput, "John");

    await waitFor(() => {
      expect(mockGetPatients).toHaveBeenLastCalledWith(expect.objectContaining({
        query: "John",
      }));
    });
  });

  it("paginates the patient directory with prev/next controls", async () => {
    mockGetPatients.mockResolvedValue({
      data: mockPatients,
      total: 250,
      page: 1,
      limit: 100,
      totalPages: 3,
    });

    render(<PatientList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/250 patients in directory/i)).toBeInTheDocument();
      expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    });

    // Initial request asks for page 1 with the backend's max page size
    await waitFor(() => {
      expect(mockGetPatients).toHaveBeenLastCalledWith(expect.objectContaining({
        page: 1,
        limit: 100,
      }));
    });
  });

  it("handles creating a new patient record", async () => {
    const user = userEvent.setup();
    render(<PatientList />, { wrapper: createWrapper() });

    // Open creation dialog
    await user.click(screen.getByRole("button", { name: /add patient/i }));
    expect(screen.getByTestId("patient-dialog")).toBeInTheDocument();

    // Click save in mocked dialog
    await user.click(screen.getByRole("button", { name: /save patient/i }));
    expect(mockGetPatients).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Patient Created',
    }));
  });

  it("handles dropdown actions (view profile, schedule, call)", async () => {
    render(<PatientList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    // View Profile
    const viewProfileBtn = screen.getAllByRole("button", { name: /view profile/i })[0];
    fireEvent.click(viewProfileBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/patients/1");

    mockNavigate.mockClear();

    // Schedule
    const scheduleBtn = screen.getAllByRole("button", { name: /schedule/i })[0];
    fireEvent.click(scheduleBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/schedule");
  });

  it("renders empty state when no patients match filters", async () => {
    mockGetPatients.mockResolvedValueOnce({
      data: [],
      total: 0,
    });

    render(<PatientList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No patients found")).toBeInTheDocument();
    });
  });

  it("handles changing the status filter", async () => {
    const user = userEvent.setup();
    render(<PatientList />, { wrapper: createWrapper() });

    // The dead sort-by / medical-alert controls were removed; the status
    // select is the only remaining filter control.
    const selects = screen.getAllByRole("combobox");
    expect(selects).toHaveLength(1);
    await user.selectOptions(selects[0], "inactive");

    await waitFor(() => {
      expect(mockGetPatients).toHaveBeenLastCalledWith(expect.objectContaining({
        status: "inactive",
        page: 1,
      }));
    });
  });
});
