// ============================================
// CoreDent PMS - Reports API Service
// API calls for analytics and reporting
// ============================================

import type { 
  DateRange, 
  DashboardMetrics,
  ReportType
} from '@/types/reports';
import type { ApiResponse } from '@/types/api';
import { format } from 'date-fns';
import { apiClient } from './api';

export const reportsApi = {
  // Get full dashboard metrics
  async getDashboardMetrics(dateRange: DateRange): Promise<ApiResponse<DashboardMetrics>> {
    // Backend expects date strings in YYYY-MM-DD format, not ISO timestamps.
    // Use LOCAL date components — toISOString() is UTC, which shifts the
    // date back a day for positive UTC offsets (e.g. IST) on local-midnight
    // dates.
    const toLocalDate = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const fromDate = toLocalDate(dateRange.from);
    const toDate = toLocalDate(dateRange.to);
    
    const response = await apiClient.get<DashboardMetrics>('/reports/dashboard', {
      from: fromDate,
      to: toDate,
    });
    
    // Return the full ApiResponse, not just the data
    return response;
  },

  // Export report as CSV
  exportToCSV(reportType: ReportType, data: DashboardMetrics, dateRange: DateRange): string {
    // CSV FORMULA-INJECTION FIX: user-controlled cells (type/month/chair)
    // are sanitized so Excel does not interpret `=cmd`, `+`, `-`, `@` as
    // formulas. Numeric server aggregates stay unquoted.
    const csvCell = (v: unknown): string => {
      const s = String(v ?? '');
      // Quote when needed for CSV structure.
      const needsQuote = /[",\n\r]/.test(s);
      // Prefix formula triggers (after optional whitespace/quotes).
      const triggersFormula = /^[ \t"']*[=+\-@]/.test(s);
      const safe = triggersFormula ? `'${s}` : s;
      if (needsQuote || triggersFormula) return `"${safe.replace(/"/g, '""')}"`;
      return safe;
    };
    let csv = '';

    switch (reportType) {
      case 'appointments':
        csv = 'Appointments Report\n';
        csv += `Date Range,${format(dateRange.from, 'MMM d, yyyy')} - ${format(dateRange.to, 'MMM d, yyyy')}\n\n`;
        csv += 'Metric,Value\n';
        csv += `Total Appointments,${data.appointments.total}\n`;
        csv += `Completed,${data.appointments.completed}\n`;
        csv += `Cancelled,${data.appointments.cancelled}\n`;
        csv += `No-Shows,${data.appointments.noShow}\n`;
        csv += `Completion Rate,${data.appointments.completionRate}%\n`;
        csv += `No-Show Rate,${data.appointments.noShowRate}%\n\n`;
        csv += 'By Type\nType,Count\n';
        data.appointments.byType.forEach(t => {
          csv += `${csvCell(t.type)},${t.count}\n`;
        });
        break;

      case 'revenue':
        csv = 'Revenue Report\n';
        csv += `Date Range,${format(dateRange.from, 'MMM d, yyyy')} - ${format(dateRange.to, 'MMM d, yyyy')}\n\n`;
        csv += 'Metric,Value\n';
        csv += `Total Revenue,$${data.revenue.totalRevenue.toLocaleString()}\n`;
        csv += `Total Collected,$${data.revenue.totalCollected.toLocaleString()}\n`;
        csv += `Outstanding,$${data.revenue.totalOutstanding.toLocaleString()}\n`;
        csv += `Avg Per Visit,$${data.revenue.averagePerVisit}\n\n`;
        csv += 'By Month\nMonth,Revenue,Collected\n';
        data.revenue.byMonth.forEach(m => {
          csv += `${csvCell(m.month)},$${m.revenue},$${m.collected}\n`;
        });
        break;

      case 'treatment':
        csv = 'Treatment Acceptance Report\n';
        csv += `Date Range,${format(dateRange.from, 'MMM d, yyyy')} - ${format(dateRange.to, 'MMM d, yyyy')}\n\n`;
        csv += 'Metric,Value\n';
        csv += `Proposed Plans,${data.treatmentAcceptance.proposedPlans}\n`;
        csv += `Accepted Plans,${data.treatmentAcceptance.acceptedPlans}\n`;
        csv += `Completed Plans,${data.treatmentAcceptance.completedPlans}\n`;
        csv += `Acceptance Rate,${data.treatmentAcceptance.acceptanceRate}%\n`;
        csv += `Completion Rate,${data.treatmentAcceptance.completionRate}%\n`;
        break;

      case 'utilization':
        csv = 'Chair Utilization Report\n';
        csv += `Date Range,${format(dateRange.from, 'MMM d, yyyy')} - ${format(dateRange.to, 'MMM d, yyyy')}\n\n`;
        csv += 'Metric,Value\n';
        csv += `Total Chairs,${data.chairUtilization.totalChairs}\n`;
        csv += `Average Utilization,${data.chairUtilization.averageUtilization}%\n\n`;
        csv += 'By Chair\nChair,Utilization,Appointments\n';
        data.chairUtilization.byChair.forEach(c => {
          csv += `${csvCell(c.chair)},${c.utilization}%,${c.appointments}\n`;
        });
        break;
    }

    return csv;
  },

  // Download CSV file
  downloadCSV(filename: string, content: string): void {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
