import React from 'react';
import type { ScheduleAppointment } from '@/types/scheduling';
import type { Chair } from '@/types/clinic';
import type { AppointmentStatus } from '@/types/api';
import { User, Clock, Stethoscope } from 'lucide-react';

interface DayViewProps {
  date: Date;
  chairs: Chair[];
  appointments: ScheduleAppointment[];
  onAppointmentClick: (appointment: ScheduleAppointment) => void;
  onStatusChange: (id: string, status: AppointmentStatus) => void;
  onEditAppointment: (appointment: ScheduleAppointment) => void;
  onCancelAppointment: (id: string) => void;
  onDropAppointment: (appointmentId: string, chairId: string, time: string) => void;
  canEdit: boolean;
}

const statusColors: Record<AppointmentStatus, string> = {
  scheduled: 'bg-blue-500/10 text-blue-600 border-blue-200 dark:border-blue-800',
  confirmed: 'bg-indigo-500/10 text-indigo-600 border-indigo-200 dark:border-indigo-800',
  checked_in: 'bg-amber-500/10 text-amber-600 border-amber-200 dark:border-amber-800',
  in_progress: 'bg-violet-500/10 text-violet-600 border-violet-200 dark:border-violet-800',
  completed: 'bg-green-500/10 text-green-600 border-green-200 dark:border-green-800',
  cancelled: 'bg-rose-500/10 text-rose-600 border-rose-200 dark:border-rose-800',
  no_show: 'bg-gray-500/10 text-gray-600 border-gray-200 dark:border-gray-800',
};

const START_HOUR = 8;
const END_HOUR = 18; // 6 PM
const HOUR_HEIGHT = 80; // pixels per hour
const MINUTE_HEIGHT = HOUR_HEIGHT / 60;

export function DayView({
  date,
  chairs,
  appointments,
  onAppointmentClick,
  onDropAppointment,
  canEdit,
}: DayViewProps) {
  // Generate time slots
  const hours = Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i);

  // Filter appointments for the current day
  const dailyAppointments = appointments.filter((appt) => {
    return (
      appt.startTime.getFullYear() === date.getFullYear() &&
      appt.startTime.getMonth() === date.getMonth() &&
      appt.startTime.getDate() === date.getDate() &&
      appt.status !== 'cancelled'
    );
  });

  const getAppointmentStyle = (appt: ScheduleAppointment) => {
    const startMins = appt.startTime.getHours() * 60 + appt.startTime.getMinutes();
    const startOffsetMins = startMins - START_HOUR * 60;
    
    // Clamp values if appointment starts before/after working hours
    const top = Math.max(0, startOffsetMins * MINUTE_HEIGHT);
    const height = appt.duration * MINUTE_HEIGHT;

    return {
      top: `${top}px`,
      height: `${height}px`,
    };
  };

  const handleDragStart = (e: React.DragEvent, id: string) => {
    e.dataTransfer.setData('text/plain', id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDrop = (e: React.DragEvent, chairId: string, hour: number, minute: number) => {
    e.preventDefault();
    const apptId = e.dataTransfer.getData('text/plain');
    if (!apptId) return;

    const timeString = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    onDropAppointment(apptId, chairId, timeString);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Operatory Chairs Headers */}
      <div className="grid grid-cols-[80px_1fr] border-b bg-muted/30">
        <div className="p-3 text-xs font-semibold text-muted-foreground text-center border-r">
          Time
        </div>
        <div className="grid" style={{ gridTemplateColumns: `repeat(${chairs.length}, minmax(150px, 1fr))` }}>
          {chairs.map((chair) => (
            <div key={chair.id} className="p-3 text-center border-r last:border-r-0 flex items-center justify-center gap-2">
              <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: chair.color }} />
              <span className="font-semibold text-sm truncate">{chair.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Grid Body */}
      <div className="flex-1 overflow-y-auto relative h-[600px]">
        <div className="grid grid-cols-[80px_1fr] relative" style={{ height: `${(END_HOUR - START_HOUR) * HOUR_HEIGHT}px` }}>
          {/* Time Labels Column */}
          <div className="border-r bg-muted/5 relative">
            {hours.map((hour) => (
              <div 
                key={hour} 
                className="text-xs text-muted-foreground text-right pr-3 font-medium select-none"
                style={{ height: `${HOUR_HEIGHT}px`, lineHeight: '20px' }}
              >
                {hour === 12 ? '12 PM' : hour > 12 ? `${hour - 12} PM` : `${hour} AM`}
              </div>
            ))}
          </div>

          {/* Chairs Columns Grid */}
          <div className="grid relative" style={{ gridTemplateColumns: `repeat(${chairs.length}, minmax(150px, 1fr))` }}>
            {/* Grid Line Drawers */}
            <div className="absolute inset-0 pointer-events-none grid grid-rows-[repeat(auto-fill,minmax(80px,1fr))]">
              {hours.map((hour) => (
                <div key={hour} className="border-b border-dashed border-muted w-full h-[80px]" />
              ))}
            </div>

            {/* Operatory Columns */}
            {chairs.map((chair) => {
              const chairAppts = dailyAppointments.filter((a) => a.chairId === chair.id);

              return (
                <div 
                  key={chair.id} 
                  className="relative border-r last:border-r-0 h-full"
                >
                  {/* Drop zones for each 30 min slot */}
                  {hours.map((hour) => (
                    <div key={hour} className="w-full" style={{ height: `${HOUR_HEIGHT}px` }}>
                      <div 
                        className="h-1/2 w-full hover:bg-accent/10 transition-colors"
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDrop(e, chair.id, hour, 0)}
                      />
                      <div 
                        className="h-1/2 w-full hover:bg-accent/10 transition-colors"
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDrop(e, chair.id, hour, 30)}
                      />
                    </div>
                  ))}

                  {/* Render Appointments */}
                  {chairAppts.map((appt) => {
                    const style = getAppointmentStyle(appt);
                    return (
                      <div
                        key={appt.id}
                        draggable={canEdit}
                        onDragStart={(e) => handleDragStart(e, appt.id)}
                        onClick={() => onAppointmentClick(appt)}
                        style={style}
                        className={`absolute left-1 right-1 p-2 rounded-lg border text-left cursor-pointer select-none transition-all hover:shadow-sm overflow-hidden flex flex-col gap-1 ${statusColors[appt.status] || 'bg-card'}`}
                      >
                        <div className="font-semibold text-xs truncate flex items-center gap-1.5">
                          <User className="h-3 w-3 text-muted-foreground shrink-0" />
                          {appt.patientName}
                        </div>
                        
                        <div className="text-[10px] opacity-80 truncate flex items-center gap-1">
                          <Clock className="h-3 w-3 shrink-0" />
                          {appt.startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - {appt.endTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>

                        {appt.duration >= 45 && (
                          <div className="text-[10px] opacity-70 truncate flex items-center gap-1 mt-auto border-t pt-1 border-muted">
                            <Stethoscope className="h-3 w-3 shrink-0" />
                            {appt.providerName || 'Dentist'}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
