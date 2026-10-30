import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/auth-context';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Users,
  Calendar,
  DollarSign,
  TrendingUp,
  Clock,
  UserPlus,
  CalendarPlus,
  FileText,
  ArrowRight,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import type { AppointmentStatus, UserRole } from '@/types/api';
import { Skeleton } from '@/components/ui/skeleton';
import { format, formatDistanceToNow, startOfMonth } from 'date-fns';
import { cn } from '@/lib/utils';
import { reportsApi } from '@/services/reportsApi';
import { appointmentsApi } from '@/services/api';
import { billingApi } from '@/services/billingApi';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';

const quickActions = [
  {
    label: 'New Patient',
    icon: UserPlus,
    href: '/patients',
    roles: ['owner', 'admin', 'front_desk'],
  },
  {
    label: 'Book Appointment',
    icon: CalendarPlus,
    href: '/schedule',
    roles: ['owner', 'admin', 'front_desk', 'dentist'],
  },
  {
    label: 'Clinical Notes',
    icon: FileText,
    href: '/notes',
    roles: ['owner', 'admin', 'dentist'],
  },
];

const statusColors: Record<AppointmentStatus, string> = {
  scheduled: 'bg-muted text-muted-foreground',
  confirmed: 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-200',
  checked_in: 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200',
  in_progress: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200',
  no_show: 'bg-red-200 text-red-900 dark:bg-red-900/70 dark:text-red-100',
};

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export default function Dashboard() {
  const { user, hasRole } = useAuth();
  const { formatCurrency } = useCurrencyFormatter({ maximumFractionDigits: 0 });
  const navigate = useNavigate();

  // Calculate date ranges
  const today = useMemo(() => new Date(), []);
  const startOfToday = useMemo(() => {
    const date = new Date(today);
    date.setHours(0, 0, 0, 0);
    return date;
  }, [today]);
  const endOfToday = useMemo(() => {
    const date = new Date(today);
    date.setHours(23, 59, 59, 999);
    return date;
  }, [today]);
  const monthStart = useMemo(() => startOfMonth(today), [today]);

  // Load dashboard metrics with React Query
  const { data: metricsResponse, isLoading: isLoadingMetrics } = useQuery({
    queryKey: ['dashboard', 'metrics', monthStart, today],
    queryFn: () => reportsApi.getDashboardMetrics({ from: monthStart, to: today }),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Extract metrics from response
  const metrics = useMemo(() => {
    return metricsResponse?.success && metricsResponse.data 
      ? metricsResponse.data 
      : null;
  }, [metricsResponse]);

  // Load today's appointments
  const { data: appointmentsResponse, isLoading: isLoadingAppointments } = useQuery({
    queryKey: ['dashboard', 'appointments', startOfToday, endOfToday],
    queryFn: () => appointmentsApi.list({ 
      startDate: startOfToday.toISOString(), 
      endDate: endOfToday.toISOString() 
    }),
    staleTime: 2 * 60 * 1000, // 2 minutes (appointments change more frequently)
  });

  // Load billing summary
  const { data: billingSummary, isLoading: isLoadingBilling } = useQuery({
    queryKey: ['dashboard', 'billing-summary'],
    queryFn: () => billingApi.getSummary(),
    staleTime: 5 * 60 * 1000,
  });

  // Extract appointments from response
  const appointments = useMemo(() => {
    return appointmentsResponse?.success && appointmentsResponse.data 
      ? appointmentsResponse.data 
      : [];
  }, [appointmentsResponse]);

  const isLoading = isLoadingMetrics || isLoadingAppointments || isLoadingBilling;

  const filteredQuickActions = quickActions.filter(action =>
    action.roles.some(role => hasRole(role as UserRole))
  );

  const uniquePatientsToday = useMemo(
    () => new Set(appointments.map(apt => apt.patientId)).size,
    [appointments]
  );
  const upcomingAppointments = useMemo(() => {
    return [...appointments]
      .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())
      .filter(apt => new Date(apt.startTime).getTime() > Date.now())
      .slice(0, 5);
  }, [appointments]);
  // Count against the full day's list: slicing to the 5-row preview first
  // capped the "X upcoming today" stat at 5.
  const upcomingCount = useMemo(
    () => appointments.filter(apt => new Date(apt.startTime).getTime() > Date.now()).length,
    [appointments]
  );
  const recentActivity = useMemo(() => {
    return [...appointments]
      .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
      .slice(0, 4)
      .map(apt => ({
        icon: Calendar,
        title: `Appointment ${apt.status.replace('_', ' ')}`,
        description: `${apt.patientName} - ${formatAppointmentType(apt.type)}`,
        time: formatDistanceToNow(new Date(apt.startTime), { addSuffix: true }),
      }));
  }, [appointments]);
  const statCards = [
    {
      title: "Today's Appointments",
      value: appointments.length,
      icon: Calendar,
      description: `${upcomingCount} upcoming today`,
      trend: 'Updated today',
      href: '/schedule',
    },
    {
      title: 'Patients Today',
      value: uniquePatientsToday,
      icon: Users,
      description: 'Unique patients',
      trend: 'Updated today',
      href: '/patients',
    },
    {
      title: 'Pending Checkouts',
      value: billingSummary?.pendingCount ?? 0,
      icon: Clock,
      description: 'Invoices awaiting payment',
      trend: 'Updated today',
      href: '/billing',
    },
    {
      title: 'Monthly Revenue',
      value: formatCurrency(metrics?.revenue.totalRevenue ?? 0),
      icon: DollarSign,
      description: format(new Date(), 'MMMM yyyy'),
      trend: 'Updated today',
      href: '/reports',
    },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-[400px] w-full" />
          <Skeleton className="h-[400px] w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {getGreeting()}, {user?.firstName}! 👋
          </h1>
          <p className="text-muted-foreground mt-1 text-lg">
            Here's what's happening at {user?.practiceName} today.
          </p>
        </div>
        
        {/* Quick Actions */}
        <div className="flex gap-2 flex-wrap">
          {filteredQuickActions.map((action) => (
            <Button 
              key={action.href} 
              variant="outline" 
              size="sm" 
              className="gap-2 h-10 px-4 shadow-sm hover:bg-secondary"
              onClick={() => navigate(action.href)}
            >
              <action.icon className="h-4 w-4" />
              <span>{action.label}</span>
            </Button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger-fade-in">
        {statCards.map((stat) => (
          <Card 
            key={stat.title} 
            className="hover:shadow-lg transition-all cursor-pointer group border-muted/60 relative overflow-hidden"
            onClick={() => navigate(stat.href)}
          >
            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
               <stat.icon className="h-16 w-16" />
            </div>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground group-hover:text-primary transition-colors">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold tracking-tight">{stat.value}</div>
              <p className="text-xs text-muted-foreground mt-1 font-medium">
                {stat.description}
              </p>
              <div className="flex items-center gap-1 mt-3 px-2 py-0.5 rounded-full bg-primary/5 w-fit text-[10px] text-primary font-bold uppercase tracking-wider">
                <TrendingUp className="h-3 w-3" />
                {stat.trend}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Today's Schedule */}
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
              {upcomingAppointments.length === 0 ? (
                <div className="text-sm text-muted-foreground">No appointments scheduled</div>
              ) : (
                upcomingAppointments.map((apt) => (
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
                      <div className="font-semibold group-hover:text-primary transition-colors">{apt.patientName}</div>
                      <div className="text-xs text-muted-foreground font-medium">{formatAppointmentType(apt.type)}</div>
                    </div>
                  </div>
                  <Badge variant="outline" className={cn("text-[10px] uppercase font-bold px-2 py-0.5 border-none", statusColors[apt.status])}>
                    {apt.status.replace('_', ' ')}
                  </Badge>
                </div>
              )))}
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="shadow-md border-muted/60">
          <CardHeader className="border-b bg-muted/5 pb-4">
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest updates from your practice</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="space-y-6">
              {recentActivity.length === 0 ? (
                <div className="text-sm text-muted-foreground">No recent activity</div>
              ) : (
                recentActivity.map((activity) => (
                  <ActivityItem
                    key={`${activity.title}-${activity.time}`}
                    icon={activity.icon}
                    title={activity.title}
                    description={activity.description}
                    time={activity.time}
                  />
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function formatAppointmentType(value: string): string {
  if (!value) return '';
  return value
    .split('_')
    .map(word => (word?.charAt(0) || '?').toUpperCase() + (word?.slice(1) || ''))
    .join(' ');
}

// Activity Item Component
function ActivityItem({ 
  icon: Icon, 
  title, 
  description, 
  time 
}: { 
  icon: React.ElementType; 
  title: string; 
  description: string; 
  time: string;
}) {
  return (
    <div className="flex gap-4 group cursor-default">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/5 border border-primary/10 group-hover:bg-primary/10 transition-colors">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="flex-1 space-y-1">
        <p className="text-sm font-bold leading-none">{title}</p>
        <p className="text-sm text-muted-foreground font-medium">{description}</p>
        <p className="text-[10px] text-muted-foreground uppercase font-black tracking-widest mt-1 opacity-60">{time}</p>
      </div>
    </div>
  );
}
