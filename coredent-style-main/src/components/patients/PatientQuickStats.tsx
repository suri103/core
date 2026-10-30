import { Card, CardContent } from '@/components/ui/card';
import {
  Calendar,
  AlertTriangle,
  StickyNote,
  Hourglass,
} from 'lucide-react';
import type { AppointmentStats } from '@/types/patient';

interface PatientQuickStatsProps {
  stats: AppointmentStats;
  notesCount: number;
}

export function PatientQuickStats({ stats, notesCount }: PatientQuickStatsProps) {
  const statCards = [
    {
      title: 'Total Visits',
      value: stats?.total ?? 0,
      subtitle: stats?.lastVisit ? `Last: ${stats.lastVisit}` : 'No previous visits',
      icon: Calendar,
      color: 'text-primary bg-primary/10 border-primary/10'
    },
    {
      title: 'Upcoming',
      value: stats?.upcoming ?? 0,
      subtitle: stats?.nextAppointment ? `Next: ${stats.nextAppointment}` : 'No upcoming visits',
      icon: Hourglass,
      color: 'text-sky-500 bg-sky-500/10 border-sky-500/10'
    },
    {
      title: 'Notes Timeline',
      value: notesCount,
      subtitle: 'Clinical & billing history',
      icon: StickyNote,
      color: 'text-purple-500 bg-purple-500/10 border-purple-500/10'
    },
    {
      title: 'No-Shows / Cancelled',
      value: `${stats?.noShow ?? 0} / ${stats?.cancelled ?? 0}`,
      subtitle: 'Cancellation rate overview',
      icon: AlertTriangle,
      color: 'text-rose-500 bg-rose-500/10 border-rose-500/10'
    }
  ];

  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
      {statCards.map((card, idx) => (
        <Card key={idx} className="border border-border bg-card/60 backdrop-blur-md">
          <CardContent className="p-4 flex items-center gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg border ${card.color}`}>
              <card.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{card.title}</p>
              <h3 className="text-xl font-bold text-foreground tracking-tight">{card.value}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{card.subtitle}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
