/**
 * DashboardScheduleCard Component
 * Displays today's schedule on the dashboard
 */

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import type { Appointment, AppointmentStatus } from '@/types/api';

const statusColors: Record<AppointmentStatus, string> = {
  scheduled: 'bg-muted text-muted-foreground',
  confirmed: 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-200',
  checked_in: 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200',
  in_progress: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200',
  no_show: 'bg-red-200 text-red-900 dark:bg-red-900/70 dark:text-red-100',
};

interface DashboardScheduleCardProps {
  appointments: Appointment[];
}

/**
 * Schedule card component for dashboard
 */
export const DashboardScheduleCard = React.memo(function DashboardScheduleCard({
  appointments,
}: DashboardScheduleCardProps) {
  const navigate = useNavigate();

  return (
    <Card className="flex flex-col shadow-md border-muted/60">
      <CardHeader className="flex flex-row items-center justify-between border-b bg-muted/5 pb-4">
        <div>
          <CardTitle>Today's Schedule</CardTitle>
          <CardDescription>Upcoming appointments</CardDescription>
        </div>
        <Link to="/schedule">
          <Button variant="ghost" size="sm" className="gap-1 hover:bg-secondary">
            View all
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent className="flex-1 pt-6">
        <div className="space-y-3">
          {appointments.length === 0 ? (
            <div className="text-sm text-muted-foreground">No appointments scheduled</div>
          ) : (
            appointments.map((apt) => (
              <div
                key={apt.id}
                className="flex items-center justify-between p-4 rounded-xl bg-muted/30 hover:bg-muted/60 transition-all border border-transparent hover:border-border cursor-pointer group"
                onClick={() => navigate(`/patients/${apt.patientId}`)}
              >
                <div className="flex items-center gap-4">
                  <div className="text-sm font-black w-16 text-primary tabular-nums">
                    {format(new Date(apt.startTime), 'h:mm a')}
                  </div>
                  <div className="w-px h-8 bg-border" />
                  <div>
                    <div className="font-semibold group-hover:text-primary transition-colors">
                      {apt.patientName}
                    </div>
                    <div className="text-xs text-muted-foreground font-medium">
                      {formatAppointmentType(apt.type)}
                    </div>
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] uppercase font-bold px-2 py-0.5 border-none",
                    statusColors[apt.status]
                  )}
                >
                  {apt.status.replace('_', ' ')}
                </Badge>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
});

DashboardScheduleCard.displayName = 'DashboardScheduleCard';

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
