import { describe, it, expect } from 'vitest';
import { useAppointmentStats } from '../useAppointmentStats';

describe('useAppointmentStats Hook', () => {
  it('should return zeros for empty appointments list', () => {
    const stats = useAppointmentStats([]);
    expect(stats).toEqual({
      total: 0,
      confirmed: 0,
      pending: 0,
      cancelled: 0,
      completed: 0,
    });
  });

  it('should calculate stats correctly for various appointment statuses', () => {
    const mockAppointments = [
      { id: '1', status: 'Confirmed', patient: 'A', time: '10:00 AM', dentist: 'D1' },
      { id: '2', status: 'pending', patient: 'B', time: '11:00 AM', dentist: 'D1' },
      { id: '3', status: 'cancelled', patient: 'C', time: '12:00 PM', dentist: 'D1' },
      { id: '4', status: 'completed', patient: 'D', time: '01:00 PM', dentist: 'D1' },
      { id: '5', status: 'CONFIRMED', patient: 'E', time: '02:00 PM', dentist: 'D1' },
      { id: '6', status: 'unknown_status', patient: 'F', time: '03:00 PM', dentist: 'D1' }, // should only increment total
    ] as any[];

    const stats = useAppointmentStats(mockAppointments);
    expect(stats).toEqual({
      total: 6,
      confirmed: 2,
      pending: 1,
      cancelled: 1,
      completed: 1,
    });
  });

  it('should handle undefined or default argument', () => {
    const stats = useAppointmentStats();
    expect(stats).toEqual({
      total: 0,
      confirmed: 0,
      pending: 0,
      cancelled: 0,
      completed: 0,
    });
  });
});
