import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { DashboardStatCard } from '../DashboardStatCard';
import { DashboardActivityCard } from '../DashboardActivityCard';
import { DashboardScheduleCard } from '../DashboardScheduleCard';

const navigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

function TestIcon() {
  return <svg aria-hidden="true" />;
}

describe('dashboard cards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the stat card and navigates on click', async () => {
    const user = userEvent.setup();

    render(
      <DashboardStatCard
        title="Revenue"
        value="$12,340"
        icon={TestIcon}
        description="Month to date"
        trend="Up 12%"
        href="/reports"
      />,
    );

    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('$12,340')).toBeInTheDocument();
    expect(screen.getByText('Month to date')).toBeInTheDocument();
    expect(screen.getByText('Up 12%')).toBeInTheDocument();

    await user.click(screen.getByText('Revenue'));
    expect(navigate).toHaveBeenCalledWith('/reports');
  });

  it('renders the activity card empty state and activity items', () => {
    const { rerender } = render(<DashboardActivityCard activities={[]} />);

    expect(screen.getByText('No recent activity')).toBeInTheDocument();

    rerender(
      <DashboardActivityCard
        activities={[
          {
            icon: TestIcon,
            title: 'Appointment confirmed',
            description: 'Maya Patel for tomorrow',
            time: '5m ago',
          },
        ]}
      />,
    );

    expect(screen.getByText('Appointment confirmed')).toBeInTheDocument();
    expect(screen.getByText('Maya Patel for tomorrow')).toBeInTheDocument();
    expect(screen.getByText('5m ago')).toBeInTheDocument();
  });

  it('renders the schedule card empty state and appointment rows', async () => {
    const user = userEvent.setup();

    const appointments = [
      {
        id: 'apt-1',
        patientId: 'patient-1',
        patientName: 'Maya Patel',
        startTime: '2026-06-27T09:00:00.000Z',
        type: 'annual_cleaning',
        status: 'confirmed',
      },
      {
        id: 'apt-2',
        patientId: 'patient-2',
        patientName: 'Sam Lee',
        startTime: '2026-06-27T10:30:00.000Z',
        type: '',
        status: 'no_show',
      },
    ] as any[];

    const { rerender } = render(
      <MemoryRouter>
        <DashboardScheduleCard appointments={[]} />
      </MemoryRouter>,
    );
    expect(screen.getByText('No appointments scheduled')).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <DashboardScheduleCard appointments={appointments} />
      </MemoryRouter>,
    );

    expect(screen.getByText('Maya Patel')).toBeInTheDocument();
    expect(screen.getByText('Annual Cleaning')).toBeInTheDocument();
    expect(screen.getByText('Sam Lee')).toBeInTheDocument();
    expect(screen.getByText('confirmed')).toBeInTheDocument();
    expect(screen.getByText('no show')).toBeInTheDocument();

    await user.click(screen.getByText('Maya Patel'));
    expect(navigate).toHaveBeenCalledWith('/patients/patient-1');
  });
});
