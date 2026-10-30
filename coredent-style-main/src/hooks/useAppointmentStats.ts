import type { Appointment } from './useAppointmentFilters';

export interface AppointmentStats {
  total: number;
  confirmed: number;
  pending: number;
  cancelled: number;
  completed: number;
}

export function useAppointmentStats(appointments: Appointment[] = []): AppointmentStats {
  return appointments.reduce(
    (stats, apt) => {
      stats.total++;
      const status = apt.status.toLowerCase();
      if (status === 'confirmed') stats.confirmed++;
      else if (status === 'pending') stats.pending++;
      else if (status === 'cancelled') stats.cancelled++;
      else if (status === 'completed') stats.completed++;
      return stats;
    },
    { total: 0, confirmed: 0, pending: 0, cancelled: 0, completed: 0 }
  );
}
