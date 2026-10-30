/**
 * useRecentActivity Hook
 * Processes appointments into recent activity items
 */

import { useMemo } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Calendar } from 'lucide-react';
import type { Appointment } from '@/types/api';

export interface ActivityItem {
  icon: React.ElementType;
  title: string;
  description: string;
  time: string;
}

interface UseRecentActivityOptions {
  limit?: number;
}

interface UseRecentActivityResult {
  activities: ActivityItem[];
}

/**
 * Hook to process appointments into recent activity items
 * 
 * @param appointments - List of appointments
 * @param options - Configuration options
 * @returns Processed activity items
 * 
 * @example
 * const { activities } = useRecentActivity(appointments, { limit: 4 });
 */
export function useRecentActivity(
  appointments: Appointment[],
  options: UseRecentActivityOptions = {}
): UseRecentActivityResult {
  const { limit = 4 } = options;

  const activities = useMemo(() => {
    return [...appointments]
      .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
      .slice(0, limit)
      .map(apt => ({
        icon: Calendar,
        title: `Appointment ${apt.status.replace('_', ' ')}`,
        description: `${apt.patientName} - ${formatAppointmentType(apt.type)}`,
        time: formatDistanceToNow(new Date(apt.startTime), { addSuffix: true }),
      }));
  }, [appointments, limit]);

  return { activities };
}

/**
 * Helper function to format appointment type
 */
function formatAppointmentType(value: string): string {
  if (!value) return '';
  return value
    .split('_')
    .map(word => (word?.charAt(0) || '?').toUpperCase() + (word?.slice(1) || ''))
    .join(' ');
}
