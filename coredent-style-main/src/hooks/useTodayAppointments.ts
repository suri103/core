/**
 * useTodayAppointments Hook
 * Fetches and manages today's appointments
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { appointmentsApi } from '@/services/api';
import type { Appointment } from '@/types/api';

interface UseTodayAppointmentsOptions {
  startDate?: Date;
  endDate?: Date;
  enabled?: boolean;
}

interface UseTodayAppointmentsResult {
  appointments: Appointment[];
  upcomingAppointments: Appointment[];
  upcomingCount: number;
  uniquePatientsCount: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook to fetch and process today's appointments
 * 
 * @param options - Configuration options
 * @returns Appointments data and statistics
 * 
 * @example
 * const { appointments, upcomingCount } = useTodayAppointments({
 *   startDate: startOfToday,
 *   endDate: endOfToday
 * });
 */
export function useTodayAppointments(
  options: UseTodayAppointmentsOptions = {}
): UseTodayAppointmentsResult {
  const { startDate, endDate, enabled = true } = options;

  // Default to the start/end of today so the query function always hands the
  // API concrete date strings (appointmentsApi.list requires them). The
  // fallback is memoized: a fresh `new Date()` per render would change the
  // queryKey on every render and refetch forever.
  const [fallbackBounds] = useState(() => new Date());
  const safeStart = startDate ?? fallbackBounds;
  const safeEnd = endDate ?? fallbackBounds;

  const { data: response, isLoading, isError, error } = useQuery({
    queryKey: ['dashboard', 'appointments', safeStart.toISOString(), safeEnd.toISOString()],
    queryFn: () => appointmentsApi.list({
      startDate: safeStart.toISOString(),
      endDate: safeEnd.toISOString(),
    }),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled,
  });

  const appointments = useMemo(() => {
    return response?.success && response.data ? response.data : [];
  }, [response]);

  const upcomingAppointments = useMemo(() => {
    return [...appointments]
      .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())
      .filter(apt => new Date(apt.startTime).getTime() > Date.now())
      .slice(0, 5);
  }, [appointments]);

  const upcomingCount = useMemo(() => {
    // Count against the full list: applying slice(0, 5) first capped the
    // "upcoming" stat at 5 even on busier days.
    return appointments.filter(
      apt => new Date(apt.startTime).getTime() > Date.now()
    ).length;
  }, [appointments]);

  const uniquePatientsCount = useMemo(() => {
    return new Set(appointments.map(apt => apt.patientId)).size;
  }, [appointments]);

  return {
    appointments,
    upcomingAppointments,
    upcomingCount,
    uniquePatientsCount,
    isLoading,
    isError,
    error: error instanceof Error ? error : null,
  };
}
