import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Schedule from "../Schedule";

// Mock Sub-components to expose easy trigger buttons for callbacks
vi.mock('@/components/scheduling/ScheduleHeader', () => ({
  ScheduleHeader: ({ onViewChange, onPrevious, onNext, onToday, onDateSelect, onNewAppointment, onOpenSearch }: any) => (
    <div data-testid="schedule-header">
      <button onClick={() => onViewChange('week')}>Change View Week</button>
      <button onClick={() => onViewChange('month')}>Change View Month</button>
      <button onClick={onPrevious}>Previous</button>
      <button onClick={onNext}>Next</button>
      <button onClick={onToday}>Today</button>
      <button onClick={() => onDateSelect(new Date())}>Select Date</button>
      <button onClick={onNewAppointment}>New Appointment</button>
      <button onClick={onOpenSearch}>Open Search</button>
    </div>
  ),
}));

vi.mock('@/components/scheduling/DayView', () => ({
  DayView: ({ onAppointmentClick, onStatusChange, onEditAppointment, onCancelAppointment, onDropAppointment }: any) => (
    <div data-testid="day-view">
      <span>Day View Component</span>
      <button onClick={() => onAppointmentClick({ id: '1', patientName: 'John Doe', startTime: new Date() })}>Click Appointment</button>
      <button onClick={() => onStatusChange('1', 'confirmed')}>Confirm Appointment</button>
      <button onClick={() => onStatusChange('1', 'completed')}>Complete Appointment</button>
      <button onClick={() => onStatusChange('1', 'no_show')}>No Show Appointment</button>
      <button onClick={() => onEditAppointment({ id: '1', patientName: 'John Doe', startTime: new Date() })}>Edit Appointment</button>
      <button onClick={() => onCancelAppointment('1')}>Cancel Appointment</button>
      <button onClick={() => onDropAppointment('1', 'chair-1', '10:00 AM')}>Drop Appointment Day</button>
    </div>
  ),
}));

vi.mock('@/components/scheduling/WeekView', () => ({
  WeekView: ({ onDropAppointment, onDayClick }: any) => (
    <div data-testid="week-view">
      <span>Week View Component</span>
      <button onClick={() => onDropAppointment('1', new Date(), '11:00 AM')}>Drop Appointment Week</button>
      <button onClick={() => onDayClick(new Date())}>Click Day</button>
    </div>
  ),
}));

vi.mock('@/components/scheduling/MonthView', () => ({
  MonthView: ({ onDayClick }: any) => (
    <div data-testid="month-view">
      <span>Month View Component</span>
      <button onClick={() => onDayClick(new Date())}>Click Day Month</button>
    </div>
  ),
}));

vi.mock('@/components/scheduling/AppointmentDialog', () => ({
  AppointmentDialog: ({ open, onSave, appointment }: any) => (
    open ? (
      <div data-testid="appointment-dialog">
        <span>Appointment Dialog</span>
        <button onClick={() => onSave({ patientId: 'p-1', patientName: appointment ? 'Updated Patient' : 'Saved Patient', providerId: 'prov-1', chairId: 'chair-1', type: 'Checkup', date: new Date(), startTime: '10:00 AM', duration: 30, notes: '' })}>Save Appointment</button>
      </div>
    ) : null
  ),
}));

vi.mock('@/components/scheduling/AppointmentDetailsSheet', () => ({
  AppointmentDetailsSheet: ({ open, onEdit, onStatusChange, onCancel }: any) => (
    open ? (
      <div data-testid="details-sheet">
        <span>Details Sheet</span>
        <button onClick={onEdit}>Edit Details</button>
        <button onClick={() => onStatusChange('confirmed')}>Confirm Details</button>
        <button onClick={onCancel}>Cancel Details</button>
      </div>
    ) : null
  ),
}));

vi.mock('@/components/scheduling/PatientSearchDialog', () => ({
  PatientSearchDialog: ({ open, onSelectPatient }: any) => (
    open ? (
      <div data-testid="patient-search-dialog">
        <span>Patient Search Dialog</span>
        <button onClick={() => onSelectPatient({ id: 'p-1', name: 'Searched Patient' })}>Select Patient</button>
      </div>
    ) : null
  ),
}));

// Mock useAuth
vi.mock('@/contexts/auth-context', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/auth-context')>();
  return {
    ...actual,
    useAuth: () => ({
      hasRole: () => true,
    }),
  };
});

// Mock Toast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

// Mock hooks
const mockGoToToday = vi.fn();
const mockGoToPrevious = vi.fn();
const mockGoToNext = vi.fn();
const mockGoToDate = vi.fn();
const mockSetView = vi.fn();
const mockAddAppointment = vi.fn();
const mockUpdateAppointment = vi.fn();
const mockLoadData = vi.fn();

const { mockUseScheduling } = vi.hoisted(() => ({
  mockUseScheduling: vi.fn(),
}));

vi.mock('@/hooks/useScheduling', () => ({
  useScheduling: mockUseScheduling,
}));

// Mock APIs
const { mockCreateAppointment, mockUpdateAppointmentApi, mockUpdateStatus, mockCancelAppointment, mockRescheduleAppointment } = vi.hoisted(() => ({
  mockCreateAppointment: vi.fn(),
  mockUpdateAppointmentApi: vi.fn(),
  mockUpdateStatus: vi.fn(),
  mockCancelAppointment: vi.fn(),
  mockRescheduleAppointment: vi.fn(),
}));

vi.mock('@/services/schedulingApi', () => ({
  schedulingApi: {
    createAppointment: mockCreateAppointment,
    updateAppointment: mockUpdateAppointmentApi,
    updateStatus: mockUpdateStatus,
    cancelAppointment: mockCancelAppointment,
    rescheduleAppointment: mockRescheduleAppointment,
  },
}));

const { mockTriggerAutomation } = vi.hoisted(() => ({
  mockTriggerAutomation: vi.fn(),
}));

vi.mock('@/services/automationApi', () => ({
  triggerAutomation: mockTriggerAutomation,
}));

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

describe("Schedule Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseScheduling.mockReturnValue({
      currentDate: new Date('2026-06-28T10:00:00Z'),
      view: 'day',
      appointments: [
        { id: '1', patientId: 'p-1', patientName: 'John Doe', startTime: new Date('2026-06-28T10:00:00Z'), endTime: new Date('2026-06-28T10:30:00Z'), duration: 30, type: 'Checkup', chairId: 'chair-1' }
      ],
      chairs: [{ id: 'chair-1', name: 'Chair 1' }],
      providers: [],
      appointmentTypes: [],
      isLoading: false,
      error: null,
      selectedAppointment: null,
      formattedDate: 'June 28, 2026',
      setView: mockSetView,
      setSelectedAppointment: vi.fn(),
      goToToday: mockGoToToday,
      goToPrevious: mockGoToPrevious,
      goToNext: mockGoToNext,
      goToDate: mockGoToDate,
      loadData: mockLoadData,
      addAppointment: mockAddAppointment,
      updateAppointment: mockUpdateAppointment,
    });
  });

  it("should render schedule page and load initial data", async () => {
    render(<Schedule />, { wrapper: createWrapper() });
    expect(mockLoadData).toHaveBeenCalled();
    expect(screen.getByTestId("day-view")).toBeInTheDocument();
  });

  it("should handle view and date navigation from header", async () => {
    const user = userEvent.setup();
    render(<Schedule />, { wrapper: createWrapper() });

    await user.click(screen.getByRole("button", { name: /change view week/i }));
    expect(mockSetView).toHaveBeenCalledWith('week');

    await user.click(screen.getByRole("button", { name: /previous/i }));
    expect(mockGoToPrevious).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(mockGoToNext).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /today/i }));
    expect(mockGoToToday).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /select date/i }));
    expect(mockGoToDate).toHaveBeenCalled();
  });

  it("should handle appointment click and status change (with automations)", async () => {
    const user = userEvent.setup();
    mockUpdateStatus.mockResolvedValue({ success: true });

    render(<Schedule />, { wrapper: createWrapper() });

    // Click appointment to open details sheet
    await user.click(screen.getByRole("button", { name: /click appointment/i }));
    expect(screen.getByTestId("details-sheet")).toBeInTheDocument();

    // Confirm appointment from day view button (which triggers status change)
    await user.click(screen.getByRole("button", { name: /confirm appointment/i }));
    expect(mockUpdateStatus).toHaveBeenCalledWith('1', 'confirmed');
    await waitFor(() => {
      expect(mockTriggerAutomation).toHaveBeenCalledWith('appointment_confirmed', expect.any(Object));
    });

    // Complete appointment
    await user.click(screen.getByRole("button", { name: /complete appointment/i }));
    expect(mockUpdateStatus).toHaveBeenCalledWith('1', 'completed');
    await waitFor(() => {
      expect(mockTriggerAutomation).toHaveBeenCalledWith('appointment_completed', expect.any(Object));
      expect(mockTriggerAutomation).toHaveBeenCalledWith('review_request', expect.any(Object));
    });

    // No-show appointment
    await user.click(screen.getByRole("button", { name: /no show appointment/i }));
    expect(mockUpdateStatus).toHaveBeenCalledWith('1', 'no_show');
    await waitFor(() => {
      expect(mockTriggerAutomation).toHaveBeenCalledWith('appointment_no_show', expect.any(Object));
    });
  });

  it("should handle editing and saving an existing appointment", async () => {
    const user = userEvent.setup();
    mockUpdateAppointmentApi.mockResolvedValue({ success: true });

    render(<Schedule />, { wrapper: createWrapper() });

    // Open edit dialog
    await user.click(screen.getByRole("button", { name: /edit appointment/i }));
    expect(screen.getByTestId("appointment-dialog")).toBeInTheDocument();

    // Click Save
    await user.click(screen.getByRole("button", { name: /save appointment/i }));
    expect(mockUpdateAppointmentApi).toHaveBeenCalledWith('1', expect.any(Object));
    expect(mockUpdateAppointment).toHaveBeenCalled();
  });

  it("should handle creating and saving a new appointment", async () => {
    const user = userEvent.setup();
    mockCreateAppointment.mockResolvedValue({ id: 'new-id', providerName: 'Dr. Smith' });

    render(<Schedule />, { wrapper: createWrapper() });

    // Open new appointment dialog
    await user.click(screen.getByRole("button", { name: /new appointment/i }));
    expect(screen.getByTestId("appointment-dialog")).toBeInTheDocument();

    // Save
    await user.click(screen.getByRole("button", { name: /save appointment/i }));
    expect(mockCreateAppointment).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockAddAppointment).toHaveBeenCalled();
      expect(mockTriggerAutomation).toHaveBeenCalledWith('appointment_booked', expect.any(Object));
    });
  });

  it("should handle cancelling an appointment", async () => {
    const user = userEvent.setup();
    mockCancelAppointment.mockResolvedValue({ success: true });

    render(<Schedule />, { wrapper: createWrapper() });

    await user.click(screen.getByRole("button", { name: /cancel appointment/i }));
    expect(mockCancelAppointment).toHaveBeenCalledWith('1');
    await waitFor(() => {
      expect(mockTriggerAutomation).toHaveBeenCalledWith('appointment_cancelled', expect.any(Object));
    });
  });

  it("should handle drag and drop rescheduling in day view", async () => {
    const user = userEvent.setup();
    mockRescheduleAppointment.mockResolvedValue({ success: true });

    render(<Schedule />, { wrapper: createWrapper() });

    await user.click(screen.getByRole("button", { name: /drop appointment day/i }));
    expect(mockRescheduleAppointment).toHaveBeenCalledWith('1', 'chair-1', expect.any(Date));
    expect(mockUpdateAppointment).toHaveBeenCalled();
  });

  it("should handle drag and drop rescheduling in week view", async () => {
    const user = userEvent.setup();
    mockUseScheduling.mockReturnValueOnce({
      ...mockUseScheduling(),
      view: 'week',
    });
    mockRescheduleAppointment.mockResolvedValue({ success: true });

    render(<Schedule />, { wrapper: createWrapper() });

    expect(screen.getByTestId("week-view")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /drop appointment week/i }));
    expect(mockRescheduleAppointment).toHaveBeenCalledWith('1', 'chair-1', expect.any(Date));
    expect(mockUpdateAppointment).toHaveBeenCalled();
  });

  it("should handle clicking a day from week view", async () => {
    const user = userEvent.setup();
    mockUseScheduling.mockReturnValueOnce({
      ...mockUseScheduling(),
      view: 'week',
    });

    render(<Schedule />, { wrapper: createWrapper() });

    await user.click(screen.getByRole("button", { name: /click day/i }));
    expect(mockGoToDate).toHaveBeenCalled();
    expect(mockSetView).toHaveBeenCalledWith('day');
  });

  it("should handle patient search and selection", async () => {
    const user = userEvent.setup();

    render(<Schedule />, { wrapper: createWrapper() });

    // Open patient search
    await user.click(screen.getByRole("button", { name: /open search/i }));
    expect(screen.getByTestId("patient-search-dialog")).toBeInTheDocument();

    // Select patient
    await user.click(screen.getByRole("button", { name: /select patient/i }));
    expect(screen.getByTestId("appointment-dialog")).toBeInTheDocument();
  });

  it("renders error state when scheduling hook returns an error", async () => {
    mockUseScheduling.mockReturnValueOnce({
      ...mockUseScheduling(),
      error: new Error("Failed to load schedule"),
    });

    render(<Schedule />, { wrapper: createWrapper() });
    expect(screen.getByRole("alert")).toHaveTextContent("Schedule data unavailable");
  });
});
