import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MonthView } from '../MonthView';

describe('MonthView', () => {
  it('renders the month grid, filters cancelled appointments, and exposes hidden counts', async () => {
    const user = userEvent.setup();
    const onDayClick = vi.fn();
    const onAppointmentClick = vi.fn();

    const appointments = [
      {
        id: 'apt-1',
        patientName: 'Maya Patel',
        status: 'confirmed',
        startTime: new Date('2026-06-27T09:00:00.000Z'),
      },
      {
        id: 'apt-2',
        patientName: 'Sam Lee',
        status: 'scheduled',
        startTime: new Date('2026-06-27T10:00:00.000Z'),
      },
      {
        id: 'apt-3',
        patientName: 'Nina Shah',
        status: 'checked_in',
        startTime: new Date('2026-06-27T11:00:00.000Z'),
      },
      {
        id: 'apt-4',
        patientName: 'Cancelled Visit',
        status: 'cancelled',
        startTime: new Date('2026-06-27T12:00:00.000Z'),
      },
      {
        id: 'apt-5',
        patientName: 'Extra Visit',
        status: 'in_progress',
        startTime: new Date('2026-06-27T13:00:00.000Z'),
      },
    ] as any[];

    render(
      <MonthView
        currentDate={new Date('2026-06-01T00:00:00.000Z')}
        appointments={appointments}
        onDayClick={onDayClick}
        onAppointmentClick={onAppointmentClick}
      />,
    );

    expect(screen.getByText('Sun')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(screen.getByText('Maya Patel')).toBeInTheDocument();
    expect(screen.getByText('Sam Lee')).toBeInTheDocument();
    expect(screen.getByText('Nina Shah')).toBeInTheDocument();
    expect(screen.queryByText('Cancelled Visit')).not.toBeInTheDocument();
    expect(screen.getByText('+ 1 more')).toBeInTheDocument();

    await user.click(screen.getByText('27'));
    expect(onDayClick).toHaveBeenCalled();

    await user.click(screen.getByText('Maya Patel'));
    expect(onAppointmentClick).toHaveBeenCalledWith(expect.objectContaining({ id: 'apt-1' }));
  });
});
