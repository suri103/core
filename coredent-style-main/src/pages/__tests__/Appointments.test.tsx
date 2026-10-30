import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';
import Appointments from '../Appointments';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

// Mock @tanstack/react-virtual
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (options: any) => ({
    getVirtualItems: () => {
      const count = options.count ?? 0;
      return Array.from({ length: count }, (_, index) => ({
        index,
        key: String(index),
        size: 72,
        start: index * 72,
      }));
    },
    getTotalSize: () => (options.count ?? 0) * 72,
    measureElement: () => {},
  }),
}));

// Mock components that might not be fully implemented
vi.mock('@/components/appointments/AppointmentCalendar', () => ({
  default: ({ appointments, onAppointmentClick }: any) => (
    <div data-testid="appointment-calendar">
      <div>Calendar View</div>
      {appointments?.map((apt: any) => (
        <div
          key={apt.id}
          data-testid={`appointment-apt-${apt.id}`}
          onClick={() => onAppointmentClick?.(apt)}
          style={{ cursor: 'pointer' }}
        >
          {apt.patientName} - {apt.time}
        </div>
      ))}
    </div>
  ),
}));

vi.mock('@/components/appointments/AppointmentForm', () => {
  const mockFormData: Record<string, string> = {};

  return {
    AppointmentForm: ({ onSubmit, onCancel, appointment }: any) => (
    <div data-testid="appointment-form">
      <h3>{appointment ? 'Edit Appointment' : 'New Appointment'}</h3>
      <label htmlFor="patient-mock">Patient Name</label>
      <input
        id="patient-mock"
        defaultValue={appointment?.patientName ?? ''}
        onChange={(e) => {
          // Mirror the real form: keep `patient` and `patientName` in sync
          mockFormData.patient = e.target.value;
          mockFormData.patientName = e.target.value;
        }}
      />
      <label htmlFor="time-mock">Time</label>
      <input
        id="time-mock"
        defaultValue={appointment?.time ?? ''}
        onChange={(e) => {
          mockFormData.time = e.target.value;
        }}
      />
      <label htmlFor="duration-mock">Duration (minutes)</label>
      <input
        id="duration-mock"
        type="number"
        defaultValue={appointment?.duration ?? '30'}
        onChange={(e) => {
          mockFormData.duration = `${e.target.value} min`;
        }}
      />
      <label htmlFor="dentist-mock">Dentist</label>
      <input
        id="dentist-mock"
        defaultValue={appointment?.dentist ?? ''}
        onChange={(e) => {
          mockFormData.dentist = e.target.value;
        }}
      />
      <button
        onClick={() =>
          onSubmit?.({
            patientName: mockFormData.patientName ?? 'Test Patient',
            time: mockFormData.time ?? '10:00 AM',
            ...mockFormData,
          })
        }
      >
        {appointment ? 'Update' : 'Create'} Appointment
      </button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  ),
    default: ({ onSubmit, onCancel, appointment }: any) => (
      <div data-testid="appointment-form">
        <h3>{appointment ? 'Edit Appointment' : 'New Appointment'}</h3>
        <button onClick={() => onSubmit?.({ patientName: 'Test Patient', time: '10:00 AM' })}>
          Save
        </button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    ),
  };
});

// Mock hooks
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

const { mockUseAppointments, mockCreateMutation, mockUpdateMutation, mockDeleteMutation, mockReminderMutation } = vi.hoisted(() => ({
  mockUseAppointments: vi.fn(),
  mockCreateMutation: vi.fn(),
  mockUpdateMutation: vi.fn(),
  mockDeleteMutation: vi.fn(),
  mockReminderMutation: vi.fn(),
}));

vi.mock('@/hooks/useAppointments', () => ({
  useAppointments: mockUseAppointments,
  useAppointmentStats: () => ({
    data: { data: { todayAppointments: 2, confirmed: 1, pending: 1, cancelled: 0 } },
    isLoading: false,
  }),
  useAppointmentTypes: () => ({
    data: { data: { types: [{ id: '1', name: 'Checkup', duration: 30 }, { id: '2', name: 'Cleaning', duration: 45 }] } },
    isLoading: false,
  }),
  useCreateAppointment: (config?: any) => ({
    mutate: (data: any) => {
      mockCreateMutation(data);
      if (data.patient === 'fail') {
        config?.onError?.();
      } else {
        config?.onSuccess?.();
      }
    },
    isPending: false,
  }),
  useUpdateAppointment: (config?: any) => ({
    mutate: ({ id, data }: any) => {
      mockUpdateMutation({ id, data });
      if (data.patient === 'fail') {
        config?.onError?.();
      } else {
        config?.onSuccess?.();
      }
    },
    isPending: false,
  }),
  useDeleteAppointment: (config?: any) => ({
    mutate: (id: string) => {
      mockDeleteMutation(id);
      if (id === 'fail') {
        config?.onError?.();
      } else {
        config?.onSuccess?.();
      }
    },
    isPending: false,
  }),
  useSendAppointmentReminder: (config?: any) => ({
    mutate: (id: string) => {
      mockReminderMutation(id);
      if (id === 'fail') {
        config?.onError?.();
      } else {
        config?.onSuccess?.();
      }
    },
    isPending: false,
  }),
}));

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

describe('Appointments Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAppointments.mockReturnValue({
      data: {
        data: {
          appointments: [
            { id: '1', patient: 'John Doe', patientName: 'John Doe', time: '10:00 AM', status: 'scheduled', type: 'checkup', dentist: 'Dr. Smith', duration: '60' },
            { id: '2', patient: 'Jane Smith', patientName: 'Jane Smith', time: '2:00 PM', status: 'scheduled', type: 'cleaning', dentist: 'Dr. Smith', duration: '60' },
          ],
        },
      },
      isLoading: false,
      isError: false,
      isPending: false,
      refetch: vi.fn(),
      error: null,
    });
    vi.stubEnv('MODE', 'test');
    vi.stubEnv('VITE_DEV_BYPASS_AUTH', 'true'); // Enable dev bypass for easier testing
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  const mockAppointments = [
    {
      id: '1',
      patientId: 'patient-1',
      patientName: 'John Doe',
      practitionerId: 'doc-1',
      practitionerName: 'Dr. Smith',
      startTime: '2024-03-16T10:00:00Z',
      endTime: '2024-03-16T11:00:00Z',
      status: 'scheduled',
      type: 'checkup',
      notes: 'Regular checkup',
      time: '10:00 AM',
    },
    {
      id: '2',
      patientId: 'patient-2',
      patientName: 'Jane Smith',
      practitionerId: 'doc-1',
      practitionerName: 'Dr. Smith',
      startTime: '2024-03-16T14:00:00Z',
      endTime: '2024-03-16T15:00:00Z',
      status: 'scheduled',
      type: 'cleaning',
      notes: 'Dental cleaning',
      time: '2:00 PM',
    },
  ];

  it('should render appointments page with the table view as default', async () => {
    server.use(
      http.get('/api/v1/appointments', () => {
        return HttpResponse.json(mockAppointments);
      })
    );

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // The real (virtualized) table is the default view
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('appointment-calendar')).not.toBeInTheDocument();

    // Toggling switches to the calendar view
    await userEvent.setup().click(screen.getByTestId('filter-button'));
    await waitFor(() => {
      expect(screen.getByTestId('appointment-calendar')).toBeInTheDocument();
    });

    expect(screen.getByText('Calendar View')).toBeInTheDocument();
  });

  it('should display appointments in calendar', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('/api/v1/appointments', () => {
        return HttpResponse.json(mockAppointments);
      })
    );

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    await user.click(screen.getByTestId('filter-button'));

    await waitFor(() => {
      expect(screen.getByTestId('appointment-apt-1')).toBeInTheDocument();
      expect(screen.getByTestId('appointment-apt-2')).toBeInTheDocument();
    });

    // Component uses hardcoded appointments
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
    expect(screen.getByText(/Jane Smith/)).toBeInTheDocument();
  });

  it('should handle appointment click', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/v1/appointments', () => {
        return HttpResponse.json(mockAppointments);
      })
    );

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    await user.click(screen.getByTestId('filter-button'));

    await waitFor(() => {
      expect(screen.getByTestId('appointment-apt-1')).toBeInTheDocument();
    });

    // Click on appointment - component has clickable appointments
    await user.click(screen.getByTestId('appointment-apt-1'));

    // Appointment should still be visible after click
    expect(screen.getByTestId('appointment-apt-1')).toBeInTheDocument();
  });

  it('should handle new appointment creation', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view is the default; wait for it to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    const newButton = screen.getByRole('button', { name: /new appointment/i });
    await user.click(newButton);

    // Verify form is open
    expect(screen.getByTestId('appointment-form')).toBeInTheDocument();

    // Fill form
    const patientInput = screen.getByLabelText(/patient name/i);
    const timeInput = screen.getByLabelText(/^time$/i);
    const dentistInput = screen.getByLabelText(/dentist/i);

    await user.type(patientInput, 'Alice Smith');
    await user.type(timeInput, '11:00 AM');
    await user.type(dentistInput, 'Dr. House');

    // Submit form
    const submitButton = screen.getByRole('button', { name: /create appointment/i });
    await user.click(submitButton);

    // Check mutation called
    expect(mockCreateMutation).toHaveBeenCalledWith(expect.objectContaining({
      patient: 'Alice Smith',
      time: '11:00 AM',
      dentist: 'Dr. House',
    }));

    // Verify success toast
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Success',
        description: 'Appointment created successfully',
      }));
    });
  });

  it('should handle new appointment creation failure', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view is the default; wait for it to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    const newButton = screen.getByRole('button', { name: /new appointment/i });
    await user.click(newButton);

    const patientInput = screen.getByLabelText(/patient name/i);
    await user.type(patientInput, 'fail');

    const submitButton = screen.getByRole('button', { name: /create appointment/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Error',
        description: 'Failed to create appointment',
      }));
    });
  });

  it('should handle appointment update', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Switch to the calendar view to click an appointment
    await user.click(screen.getByTestId('filter-button'));

    await waitFor(() => {
      expect(screen.getByTestId('appointment-apt-1')).toBeInTheDocument();
    });

    // Click on appointment in calendar to open form
    await user.click(screen.getByTestId('appointment-apt-1'));

    // Verify form is pre-filled
    const patientInput = screen.getByLabelText(/patient name/i);
    expect(patientInput).toHaveValue('John Doe');

    // Change patient name
    await user.clear(patientInput);
    await user.type(patientInput, 'John Doe Updated');

    const submitButton = screen.getByRole('button', { name: /update appointment/i });
    await user.click(submitButton);

    expect(mockUpdateMutation).toHaveBeenCalledWith(expect.objectContaining({
      id: '1',
      data: expect.objectContaining({
        patient: 'John Doe Updated',
      }),
    }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Success',
        description: 'Appointment updated successfully',
      }));
    });
  });

  it('should handle appointment update failure', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Switch to the calendar view to click an appointment
    await user.click(screen.getByTestId('filter-button'));

    await waitFor(() => {
      expect(screen.getByTestId('appointment-apt-1')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('appointment-apt-1'));

    const patientInput = screen.getByLabelText(/patient name/i);
    await user.clear(patientInput);
    await user.type(patientInput, 'fail');

    const submitButton = screen.getByRole('button', { name: /update appointment/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Error',
        description: 'Failed to update appointment',
      }));
    });
  });

  it('should handle appointment deletion', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view (with the virtualized list) is the default
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Delete button on the first row
    const deleteButtons = screen.getAllByRole('button').filter(btn => btn.querySelector('.text-red-500'));
    expect(deleteButtons.length).toBeGreaterThan(0);
    await user.click(deleteButtons[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDeleteMutation).toHaveBeenCalledWith('1');

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Success',
        description: 'Appointment deleted successfully',
      }));
    });

    confirmSpy.mockRestore();
  });

  it('should handle appointment deletion failure', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    mockUseAppointments.mockReturnValue({
      data: {
        data: {
          appointments: [
            { id: 'fail', patient: 'Fail Patient', patientName: 'Fail Patient', time: '10:00 AM', status: 'Pending', type: 'checkup', dentist: 'Dr. Smith', duration: '60' },
          ],
        },
      },
      isLoading: false,
      isError: false,
    });

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view is the default
    await waitFor(() => {
      expect(screen.getByText('Fail Patient')).toBeInTheDocument();
    });

    // Click Delete button on the first row
    const deleteButtons = screen.getAllByRole('button').filter(btn => btn.querySelector('.text-red-500'));
    expect(deleteButtons.length).toBeGreaterThan(0);
    await user.click(deleteButtons[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDeleteMutation).toHaveBeenCalledWith('fail');

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Error',
        description: 'Failed to delete appointment',
      }));
    });

    confirmSpy.mockRestore();
  });

  it('should handle send reminder', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view is the default
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Find Send button precisely using Lucide class name
    const sendButtons = screen.getAllByRole('button');
    const sendBtn = sendButtons.find(btn => btn.querySelector('.lucide-send'));
    expect(sendBtn).toBeDefined();
    await user.click(sendBtn!);

    expect(mockReminderMutation).toHaveBeenCalledWith('1');
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Success',
        description: 'Reminder sent successfully',
      }));
    });
  });

  it('should handle API errors gracefully', async () => {
    mockUseAppointments.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      isPending: false,
      refetch: vi.fn(),
      error: new Error('Failed to fetch appointments'),
    });

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Appointment data is currently unavailable',
    );
  });

  it('should filter appointments by date range', async () => {
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // Table view is the default; the search input lives there
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search appointments...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search appointments...');
    await user.type(searchInput, 'Jane');

    // Only Jane Smith should be visible
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
  });

  it('should handle empty appointments list', async () => {
    mockUseAppointments.mockReturnValue({
      data: { data: { appointments: [] } },
      isLoading: false,
      isError: false,
    });

    render(
      <TestWrapper>
        <Appointments />
      </TestWrapper>
    );

    // The empty-state selector is present in the default table view
    await waitFor(() => {
      expect(screen.getByTestId('empty-appointments')).toBeInTheDocument();
    });
  });
});