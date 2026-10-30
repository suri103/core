import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { ScheduleAppointment } from '@/types/scheduling';
import type { AppointmentStatus } from '@/types/api';
import { 
  User, 
  Calendar, 
  Clock, 
  FileText, 
  Stethoscope, 
  MapPin, 
  Trash2, 
  Edit 
} from 'lucide-react';

interface AppointmentDetailsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointment: ScheduleAppointment | null;
  onEdit: () => void;
  onStatusChange: (status: AppointmentStatus) => void;
  onCancel: () => void;
  canEdit: boolean;
}

const statusColors: Record<AppointmentStatus, string> = {
  scheduled: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  confirmed: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400',
  checked_in: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  in_progress: 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  cancelled: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400',
  no_show: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
};

const formatStatus = (status: string) => {
  return status.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
};

export function AppointmentDetailsSheet({
  open,
  onOpenChange,
  appointment,
  onEdit,
  onStatusChange,
  onCancel,
  canEdit,
}: AppointmentDetailsSheetProps) {
  if (!appointment) return null;

  const dateStr = appointment.startTime.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  const timeStr = `${appointment.startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${appointment.endTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[450px] overflow-y-auto">
        <SheetHeader className="pb-4 border-b">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-xl">Appointment Details</SheetTitle>
            <Badge className={`${statusColors[appointment.status as AppointmentStatus] || 'bg-secondary'} border-none mr-4 capitalize`}>
              {formatStatus(appointment.status)}
            </Badge>
          </div>
        </SheetHeader>

        <div className="py-6 space-y-6">
          {/* Patient Details */}
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
              <User className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Patient</h3>
              <p className="text-base font-medium">{appointment.patientName}</p>
              {appointment.patientPhone && <p className="text-sm text-muted-foreground">{appointment.patientPhone}</p>}
              {appointment.patientEmail && <p className="text-sm text-muted-foreground">{appointment.patientEmail}</p>}
            </div>
          </div>

          {/* Date & Time */}
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
              <Calendar className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Date</h3>
              <p className="text-base font-medium">{dateStr}</p>
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground mt-0.5">
                <Clock className="h-3.5 w-3.5" />
                <span>{timeStr} ({appointment.duration} mins)</span>
              </div>
            </div>
          </div>

          {/* Provider / Dentist */}
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
              <Stethoscope className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Provider</h3>
              <p className="text-base font-medium">{appointment.providerName || 'Unassigned'}</p>
            </div>
          </div>

          {/* Operatory / Chair */}
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
              <MapPin className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Operatory / Chair</h3>
              <p className="text-base font-medium">{appointment.chairName || 'Unassigned'}</p>
            </div>
          </div>

          {/* Appointment Type */}
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground">Appointment Type</h3>
              <p className="text-base font-medium capitalize">{appointment.type.replace('_', ' ')}</p>
            </div>
          </div>

          {/* Notes */}
          {appointment.notes && (
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 mt-1 shrink-0">
                <FileText className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-muted-foreground">Notes</h3>
                <p className="text-sm bg-accent/30 p-3 rounded-lg border mt-1 whitespace-pre-wrap">
                  {appointment.notes}
                </p>
              </div>
            </div>
          )}

          {/* Actions & Status Updates */}
          {canEdit && (
            <div className="pt-6 border-t space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-muted-foreground">Update Status</label>
                <Select
                  value={appointment.status}
                  onValueChange={(val) => onStatusChange(val as AppointmentStatus)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="confirmed">Confirmed</SelectItem>
                    <SelectItem value="checked_in">Checked In</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="no_show">No Show</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <Button variant="outline" className="flex-1 gap-1" onClick={onEdit}>
                  <Edit className="h-4 w-4" />
                  Edit
                </Button>
                
                {appointment.status !== 'cancelled' && (
                  <Button variant="destructive" className="flex-1 gap-1" onClick={onCancel}>
                    <Trash2 className="h-4 w-4" />
                    Cancel Appt
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
