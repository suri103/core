/**
 * Appointments Page Integration Tests
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';
import Appointments from '../Appointments';
import type { Appointment } from '@/services/appointmentsApi';
import { useAppointments, useAppointmentTypes } from '@/hooks/useAppointments';

// Mock the hooks
vi.mock('@/hooks/useAppointments', () => ({
  useAppointments: vi.fn(),
  useAppointmentStats: vi.fn().mockReturnValue({
    data: { data: { todayAppointments: 2, confirmed: 1, pending: 1, cancelled: 0 } },
    isLoading: false,
  }),
  useAppointmentTypes: vi.fn(),
  useCreateAppointment: vi.fn().mockReturnValue({ mutate: vi.fn(), isPending: false }),
  useUpdateAppointment: vi.fn().mockReturnValue({ mutate: vi.fn(), isPending: false }),
  useDeleteAppointment: vi.fn().mockReturnValue({ mutate: vi.fn(), isPending: false }),
  useSendAppointmentReminder: vi.fn().mockReturnValue({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

const mockAppointments: Appointment[] = [
  {
    id: '1',
    patientId: 'p1',
    patient: 'John Doe',
    patientName: 'John Doe',
    providerId: 'd1',
    providerName: 'Dr. Smith',
    startTime: '2026-08-12T13:00:00.000Z',
    endTime: '2026-08-12T13:30:00.000Z',
    time: '9:00 AM',
    duration: '30',
    type: 'Checkup',
    dentist: 'Dr. Smith',
    status: 'confirmed',
  },
  {
    id: '2',
    patientId: 'p2',
    patient: 'Jane Smith',
    patientName: 'Jane Smith',
    providerId: 'd2',
    providerName: 'Dr. Jones',
    startTime: '2026-08-12T14:00:00.000Z',
    endTime: '2026-08-12T14:45:00.000Z',
    time: '10:00 AM',
    duration: '45',
    type: 'Cleaning',
    dentist: 'Dr. Jones',
    status: 'scheduled',
  },
];

const mockAppointmentTypes = [
  { id: '1', name: 'Checkup', duration: 30 },
  { id: '2', name: 'Cleaning', duration: 45 },
];

describe('Appointments Page Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    (window as any).__INTEGRATION_TEST__ = true;
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  const renderWithProviders = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        {component}
      </QueryClientProvider>
    );
  };

  it('should load and display appointments', async () => {
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  it('should display appointment statistics', async () => {
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    await waitFor(() => {
      // Use getAllByText since 'Confirmed'/'Pending' appear in both stat cards and appointment badges
      expect(screen.getAllByText(/Today.*Appointments/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Confirmed/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Pending/i).length).toBeGreaterThan(0);
    });
  });

  it('should filter appointments by search term', async () => {
    const user = userEvent.setup();
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    const searchInput = screen.getByPlaceholderText('Search appointments...');
    await user.type(searchInput, 'John');

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('should display loading state', () => {
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: [] } },
      isLoading: true,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: [] } },
    });

    renderWithProviders(<Appointments />);

    expect(screen.getByText('Loading appointments...')).toBeInTheDocument();
  });

  it('should display empty state when no appointments', async () => {
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: [] } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    await waitFor(() => {
      expect(screen.getByText('No appointments found')).toBeInTheDocument();
    });
  });

  it('should switch between list and timeline views', async () => {
    const user = userEvent.setup();
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    const timelineTab = screen.getByRole('tab', { name: /Timeline/i });
    await user.click(timelineTab);

    await waitFor(() => {
      expect(screen.getByText(/Timeline View/)).toBeInTheDocument();
    });
  });

  it('should display appointment types', async () => {
    const user = userEvent.setup();
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    const typesTab = screen.getByRole('tab', { name: /Appointment Types/i });
    await user.click(typesTab);

    await waitFor(() => {
      expect(screen.getByText('Checkup')).toBeInTheDocument();
      expect(screen.getByText('Cleaning')).toBeInTheDocument();
    });
  });

  it('should open new appointment form', async () => {
    const user = userEvent.setup();
    (useAppointments as any).mockReturnValue({
      data: { data: { appointments: mockAppointments } },
      isLoading: false,
    });

    (useAppointmentTypes as any).mockReturnValue({
      data: { data: { types: mockAppointmentTypes } },
    });

    renderWithProviders(<Appointments />);

    const newButton = screen.getByRole('button', { name: /New Appointment/i });
    await user.click(newButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});
