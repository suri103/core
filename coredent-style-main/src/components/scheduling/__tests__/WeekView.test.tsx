import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WeekView } from '../WeekView';

describe('WeekView', () => {
  it('renders the weekly grid, day links, and appointment cards', async () => {
    const user = userEvent.setup();
    const onAppointmentClick = vi.fn();
    const onDropAppointment = vi.fn();
    const onDayClick = vi.fn();

    const appointments = [
      {
        id: 'apt-1',
        patientName: 'Maya Patel',
        status: 'confirmed',
        startTime: new Date('2026-06-27T09:00:00.000Z'),
        duration: 30,
      },
      {
        id: 'apt-2',
        patientName: 'Sam Lee',
        status: 'cancelled',
        startTime: new Date('2026-06-27T10:00:00.000Z'),
        duration: 30,
      },
    ] as any[];

    const { container } = render(
      <WeekView
        currentDate={new Date('2026-06-27T00:00:00.000Z')}
        appointments={appointments}
        onAppointmentClick={onAppointmentClick}
        onStatusChange={vi.fn()}
        onEditAppointment={vi.fn()}
        onCancelAppointment={vi.fn()}
        onDropAppointment={onDropAppointment}
        onDayClick={onDayClick}
        canEdit
      />,
    );

    expect(screen.getByText('Time')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(screen.getByText('Maya Patel')).toBeInTheDocument();
    expect(screen.queryByText('Sam Lee')).not.toBeInTheDocument();

    await user.click(screen.getByText('27'));
    expect(onDayClick).toHaveBeenCalled();

    await user.click(screen.getByText('Maya Patel'));
    expect(onAppointmentClick).toHaveBeenCalledWith(expect.objectContaining({ id: 'apt-1' }));

    const dragTarget = container.querySelector('[draggable="true"]') as HTMLElement | null;
    expect(dragTarget).toBeTruthy();
    if (dragTarget) {
      fireEvent.dragStart(dragTarget, {
        dataTransfer: {
          setData: vi.fn(),
          effectAllowed: '',
          getData: vi.fn(() => 'apt-1'),
        },
      } as never);
    }

    expect(onDropAppointment).not.toHaveBeenCalled();
  });
});
