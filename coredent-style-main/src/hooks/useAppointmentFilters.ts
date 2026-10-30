import { useMemo } from 'react';

export interface AppointmentFilters {
  searchTerm?: string;
  status?: string;
  dentist?: string;
}

export interface Appointment {
  id: string;
  patient: string;
  patientName: string;
  status: string;
  time: string;
  type: string;
  dentist: string;
  duration: string;
}

export function useAppointmentFilters(
  appointments: Appointment[],
  filters: AppointmentFilters
): Appointment[] {
  return useMemo(() => {
    return appointments.filter((apt) => {
      if (filters.searchTerm) {
        const term = filters.searchTerm.toLowerCase();
        const searchable = `${apt.patient} ${apt.patientName} ${apt.type} ${apt.dentist}`.toLowerCase();
        if (!searchable.includes(term)) return false;
      }
      if (filters.status && apt.status !== filters.status) return false;
      if (filters.dentist && apt.dentist !== filters.dentist) return false;
      return true;
    });
  }, [appointments, filters]);
}

export function useUniqueDentists(appointments: Appointment[]): string[] {
  return useMemo(() => {
    const dentists = [...new Set(appointments.map((apt) => apt.dentist))];
    return dentists.sort();
  }, [appointments]);
}

export function getStatusColor(status: string): string {
  const normalized = status.toLowerCase();
  switch (normalized) {
    case 'confirmed':
      return 'bg-green-500';
    case 'pending':
      return 'bg-yellow-500';
    case 'cancelled':
      return 'bg-red-500';
    case 'completed':
      return 'bg-blue-500';
    default:
      return 'bg-gray-500';
  }
}
