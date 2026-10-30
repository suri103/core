/**
 * AppointmentForm Component Tests
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { AppointmentForm } from '../appointments/AppointmentForm';
import type { Appointment } from '@/services/appointmentsApi';

describe('AppointmentForm', () => {
  const mockAppointmentTypes = [
    { id: '1', name: 'Checkup', duration: 30 },
    { id: '2', name: 'Cleaning', duration: 45 },
    { id: '3', name: 'Root Canal', duration: 60 },
  ];

  it('should render form with empty fields for new appointment', () => {
    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByPlaceholderText('Enter patient name')).toHaveValue('');
    expect(screen.getByPlaceholderText('e.g., 9:00 AM')).toHaveValue('');
  });

  it('should populate form with appointment data for editing', () => {
    const appointment: Appointment = {
      id: '1',
      patientId: 'p1',
      patient: 'John Doe',
      patientName: 'John Doe',
      providerId: 'doc1',
      providerName: 'Dr. Smith',
      startTime: '2026-08-12T13:00:00.000Z',
      endTime: '2026-08-12T13:30:00.000Z',
      time: '9:00 AM',
      duration: '30',
      type: 'Checkup',
      dentist: 'Dr. Smith',
      status: 'confirmed',
    };

    render(
      <AppointmentForm
        appointment={appointment}
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('9:00 AM')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Dr. Smith')).toBeInTheDocument();
  });

  it('should call onSubmit with form data', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    );

    await user.type(screen.getByPlaceholderText('Enter patient name'), 'Jane Doe');
    await user.type(screen.getByPlaceholderText('e.g., 9:00 AM'), '10:00 AM');
    await user.type(screen.getByPlaceholderText('e.g., Dr. Wilson'), 'Dr. Jones');

    const submitButton = screen.getByRole('button', { name: /Create Appointment/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
  });

  it('should call onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />
    );

    const cancelButton = screen.getByRole('button', { name: /Cancel/i });
    await user.click(cancelButton);

    expect(onCancel).toHaveBeenCalled();
  });

  it('should display appointment types in select', () => {
    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText('Select type')).toBeInTheDocument();
  });

  it('should display status select with default value', () => {
    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const statusSelect = screen.getByDisplayValue('Pending');
    expect(statusSelect).toBeInTheDocument();
  });

  it('should show Update button for existing appointment', () => {
    const appointment: Appointment = {
      id: '1',
      patientId: 'p1',
      patient: 'John Doe',
      patientName: 'John Doe',
      providerId: 'doc1',
      providerName: 'Dr. Smith',
      startTime: '2026-08-12T13:00:00.000Z',
      endTime: '2026-08-12T13:30:00.000Z',
      time: '9:00 AM',
      duration: '30',
      type: 'Checkup',
      dentist: 'Dr. Smith',
      status: 'confirmed',
    };

    render(
      <AppointmentForm
        appointment={appointment}
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Update Appointment/i })).toBeInTheDocument();
  });

  it('should show Create button for new appointment', () => {
    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Create Appointment/i })).toBeInTheDocument();
  });

  it('should update form fields when user types', async () => {
    const user = userEvent.setup();

    render(
      <AppointmentForm
        appointmentTypes={mockAppointmentTypes}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const patientInput = screen.getByPlaceholderText('Enter patient name');
    await user.type(patientInput, 'Jane Doe');

    expect(patientInput).toHaveValue('Jane Doe');
  });

  it('should handle empty appointment types', () => {
    render(
      <AppointmentForm
        appointmentTypes={[]}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByPlaceholderText('Enter patient name')).toBeInTheDocument();
  });
});
