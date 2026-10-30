import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Calendar,
  Clock,
  User,
  MapPin,
} from 'lucide-react';

interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  providerId: string;
  providerName: string;
  chairId: string;
  chairName: string;
  appointmentTypeId: string;
  appointmentTypeName: string;
  date: string;
  startTime: string;
  endTime: string;
  status: 'scheduled' | 'confirmed' | 'checked_in' | 'in_progress' | 'completed' | 'cancelled' | 'no_show';
  notes?: string;
}

interface AppointmentHistoryProps {
  appointments: Appointment[];
}

export function AppointmentHistory({ appointments }: AppointmentHistoryProps) {
  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'confirmed':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'checked_in':
      case 'in_progress':
        return 'bg-sky-500/10 text-sky-500 border-sky-500/20';
      case 'cancelled':
        return 'bg-neutral-500/10 text-neutral-500 border-neutral-500/20';
      case 'no_show':
        return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
      default:
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20'; // scheduled
    }
  };

  return (
    <Card className="border border-border bg-card/60 backdrop-blur-md">
      <CardContent className="p-6 space-y-4">
        {appointments && appointments.length > 0 ? (
          <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
            {appointments.map((apt) => (
              <div key={apt.id} className="rounded-xl border border-border bg-accent/20 p-4 space-y-3 hover:border-primary/20 transition-all">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-foreground capitalize">
                      {apt.appointmentTypeName || 'General Cleaning'}
                    </span>
                    <Badge variant="outline" className={`${getStatusBadgeColor(apt.status)} capitalize border text-[10px] px-1.5 py-0`}>
                      {apt.status.replace('_', ' ')}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Calendar className="h-3.5 w-3.5" />
                    <span>{apt.date}</span>
                    <Clock className="h-3.5 w-3.5 ml-1.5" />
                    <span>{apt.startTime} - {apt.endTime}</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-1">
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <User className="h-3.5 w-3.5 text-muted-foreground/75" />
                    <span>Dentist: <strong className="text-foreground font-medium">{apt.providerName || 'Dr. House'}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5 text-muted-foreground/75" />
                    <span>Operatory: <strong className="text-foreground font-medium">{apt.chairName || 'Chair 1'}</strong></span>
                  </div>
                </div>

                {apt.notes && (
                  <div className="text-xs bg-background/50 rounded-lg p-2.5 text-muted-foreground leading-relaxed border border-border/40">
                    {apt.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border/80 p-8 text-center text-sm text-muted-foreground bg-accent/5">
            <Calendar className="h-10 w-10 mx-auto opacity-40 mb-3 text-muted-foreground" />
            <p className="font-medium">No appointments scheduled</p>
            <p className="text-xs mt-1">Patient has no previous visits or upcoming schedules.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
