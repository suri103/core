import type { Appointment } from '@/services/appointmentsApi';

interface AppointmentTimelineViewProps {
  appointments?: Appointment[];
  isLoading?: boolean;
}

export function AppointmentTimelineView({ appointments, isLoading }: AppointmentTimelineViewProps) {
  if (isLoading) return <div>Loading timeline...</div>;
  if (!appointments?.length) return <div>No appointments for timeline</div>;
  return <div>Timeline View ({appointments.length} appointments)</div>;
}
