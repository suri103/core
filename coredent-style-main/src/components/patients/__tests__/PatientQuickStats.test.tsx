import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PatientQuickStats } from '../PatientQuickStats';

const fullStats = {
  total: 12,
  completed: 10,
  cancelled: 1,
  noShow: 1,
  upcoming: 2,
  lastVisit: '2026-06-01',
  nextAppointment: '2026-07-01',
};

describe('PatientQuickStats', () => {
  it('shows populated visit and note stats', () => {
    render(<PatientQuickStats stats={fullStats} notesCount={3} />);

    expect(screen.getByText('Total Visits')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Last: 2026-06-01')).toBeInTheDocument();
    expect(screen.getByText('Upcoming')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Notes Timeline')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('No-Shows / Cancelled')).toBeInTheDocument();
    expect(screen.getByText('1 / 1')).toBeInTheDocument();
  });

  it('falls back when dates are missing', () => {
    render(
      <PatientQuickStats
        stats={{ total: 0, completed: 0, cancelled: 0, noShow: 0, upcoming: 0 }}
        notesCount={0}
      />,
    );

    expect(screen.getByText('No previous visits')).toBeInTheDocument();
    expect(screen.getByText('No upcoming visits')).toBeInTheDocument();
    expect(screen.getByText('0 / 0')).toBeInTheDocument();
  });
});
