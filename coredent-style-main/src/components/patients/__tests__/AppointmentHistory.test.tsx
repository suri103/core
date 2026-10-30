import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AppointmentHistory } from '../AppointmentHistory';

describe('AppointmentHistory', () => {
  it('renders the empty state', () => {
    render(<AppointmentHistory appointments={[]} />);

    expect(screen.getByText('No appointments scheduled')).toBeInTheDocument();
    expect(screen.getByText('Patient has no previous visits or upcoming schedules.')).toBeInTheDocument();
  });

  it('renders appointment rows and fallback labels', () => {
    render(
      <AppointmentHistory
        appointments={[
          {
            id: 'apt-1',
            patientId: 'patient-1',
            patientName: 'Maya Patel',
            providerId: 'prov-1',
            providerName: '',
            chairId: 'chair-1',
            chairName: '',
            appointmentTypeId: 'type-1',
            appointmentTypeName: '',
            date: '2026-06-27',
            startTime: '09:00 AM',
            endTime: '09:30 AM',
            status: 'checked_in',
            notes: 'Arrived early',
          },
        ]}
      />,
    );

    expect(screen.getByText('General Cleaning')).toBeInTheDocument();
    expect(screen.getByText('checked in')).toBeInTheDocument();
    expect(screen.getByText('2026-06-27')).toBeInTheDocument();
    expect(screen.getByText('09:00 AM - 09:30 AM')).toBeInTheDocument();
    expect(screen.getByText(/Dentist:/)).toBeInTheDocument();
    expect(screen.getByText('Dr. House')).toBeInTheDocument();
    expect(screen.getByText(/Operatory:/)).toBeInTheDocument();
    expect(screen.getByText('Chair 1')).toBeInTheDocument();
    expect(screen.getByText('Arrived early')).toBeInTheDocument();
  });
});
