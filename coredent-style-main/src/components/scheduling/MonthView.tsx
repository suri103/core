import type { ScheduleAppointment } from '@/types/scheduling';
import type { AppointmentStatus } from '@/types/api';

interface MonthViewProps {
  currentDate: Date;
  appointments: ScheduleAppointment[];
  onDayClick: (date: Date) => void;
  onAppointmentClick: (appointment: ScheduleAppointment) => void;
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

export function MonthView({
  currentDate,
  appointments,
  onDayClick,
  onAppointmentClick,
}: MonthViewProps) {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // First day of current month
  const firstDay = new Date(year, month, 1);
  const startDayOfWeek = firstDay.getDay();

  // Calendar grid start date (padding from previous month)
  const gridStartDate = new Date(firstDay);
  gridStartDate.setDate(firstDay.getDate() - startDayOfWeek);

  // Generate 42 calendar grid days (6 weeks)
  const gridDays = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStartDate);
    d.setDate(gridStartDate.getDate() + i);
    return d;
  });

  const weekHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  // Filter out cancelled appointments
  const activeAppointments = appointments.filter((appt) => appt.status !== 'cancelled');

  const isToday = (d: Date) => {
    const today = new Date();
    return (
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear()
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden select-none">
      {/* Month Days Header */}
      <div className="grid grid-cols-7 border-b bg-muted/30">
        {weekHeaders.map((hdr) => (
          <div key={hdr} className="p-2 text-xs font-semibold text-muted-foreground text-center border-r last:border-r-0">
            {hdr}
          </div>
        ))}
      </div>

      {/* Grid Days */}
      <div className="grid grid-cols-7 grid-rows-6 flex-1 min-h-[500px]">
        {gridDays.map((dayDate) => {
          const dayNum = dayDate.getDate();
          const isCurrentMonth = dayDate.getMonth() === month;
          const cellMutedClass = isCurrentMonth ? '' : 'text-muted-foreground/40 bg-muted/5';
          const todayClass = isToday(dayDate) ? 'bg-primary text-primary-foreground rounded-full w-6 h-6 flex items-center justify-center font-bold text-xs' : 'text-xs font-semibold';

          // Daily appointments
          const dayAppts = activeAppointments.filter((appt) => {
            return (
              appt.startTime.getDate() === dayDate.getDate() &&
              appt.startTime.getMonth() === dayDate.getMonth() &&
              appt.startTime.getFullYear() === dayDate.getFullYear()
            );
          });

          // Slice to show up to 3 appointments inside grid, and badge the rest
          const displayedAppts = dayAppts.slice(0, 3);
          const hiddenCount = dayAppts.length - 3;

          return (
            <div
              key={dayDate.toISOString()}
              className={`border-r border-b last:border-r-0 p-1 flex flex-col items-stretch justify-start min-h-[85px] transition-colors hover:bg-accent/5 ${cellMutedClass}`}
            >
              {/* Day Number Row */}
              <div className="flex justify-between items-center p-1">
                <button
                  onClick={() => onDayClick(dayDate)}
                  className={`hover:bg-accent p-1 rounded-full transition-colors ${todayClass}`}
                >
                  {dayNum}
                </button>
              </div>

              {/* Day Appointments List */}
              <div className="flex-1 space-y-1 overflow-hidden pb-1">
                {displayedAppts.map((appt) => {
                  const timeStr = appt.startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                  return (
                    <button
                      key={appt.id}
                      onClick={(e) => {
                        e.stopPropagation(); // Avoid triggering day click
                        onAppointmentClick(appt);
                      }}
                      className={`w-full text-[10px] text-left p-1 rounded px-1.5 truncate border cursor-pointer block font-medium hover:brightness-95 transition-all ${statusColors[appt.status] || 'bg-card'}`}
                    >
                      <span className="font-semibold mr-1">{timeStr}</span>
                      {appt.patientName}
                    </button>
                  );
                })}

                {hiddenCount > 0 && (
                  <button
                    onClick={() => onDayClick(dayDate)}
                    className="text-[9px] text-muted-foreground font-semibold px-1.5 hover:underline text-left block w-full mt-0.5 cursor-pointer"
                  >
                    + {hiddenCount} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
