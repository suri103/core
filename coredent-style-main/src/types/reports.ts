// ============================================
// CoreDent PMS - Reports Types
// ============================================

export type ReportType = 'appointments' | 'revenue' | 'treatment' | 'utilization';

export interface DateRange {
  from: Date;
  to: Date;
}

export interface AppointmentTypeMetric {
  type: string;
  count: number;
}

export interface AppointmentDayMetric {
  // Wire shape from app/schemas/reports.py (AppointmentTrendPoint): the backend
  // emits {day, count}. The previous {date, appointments} type matched neither
  // the API nor the chart, so the trend chart rendered empty axes.
  day: string;
  count: number;
}

export interface RevenueMonthMetric {
  month: string;
  revenue: number;
  collected: number;
}

export interface RevenueProcedureMetric {
  procedure: string;
  revenue: number;
}

export interface ChairMetric {
  chair: string;
  utilization: number;
  appointments: number;
}

export interface PeakHourMetric {
  hour: string;
  utilization: number;
}

export interface DayOfWeekMetric {
  day: string;
  utilization: number;
}

export interface DashboardMetrics {
  appointments: {
    total: number;
    completed: number;
    cancelled: number;
    noShow: number;
    completionRate: number;
    noShowRate: number;
    byType: AppointmentTypeMetric[];
    byDay: AppointmentDayMetric[];
  };
  revenue: {
    totalRevenue: number;
    totalCollected: number;
    totalOutstanding: number;
    averagePerVisit: number;
    byMonth: RevenueMonthMetric[];
    byProcedure: RevenueProcedureMetric[];
  };
  treatmentAcceptance: {
    proposedPlans: number;
    acceptedPlans: number;
    completedPlans: number;
    acceptanceRate: number;
    completionRate: number;
  };
  chairUtilization: {
    averageUtilization: number;
    totalChairs: number;
    peakHours: PeakHourMetric[];
    byChair: ChairMetric[];
    byDayOfWeek: DayOfWeekMetric[];
  };
}
