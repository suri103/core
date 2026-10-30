import {
  BarChart, 
  Bar 
} from 'recharts';
import { 
  BaseChart, 
  ChartGrid, 
  ChartXAxis, 
  ChartYAxis, 
  ChartTooltip 
} from './BaseChart';
import type { AppointmentDayMetric } from '@/types/reports';

interface DailyAppointmentsChartProps {
  data: AppointmentDayMetric[];
}

export function DailyAppointmentsChart({ data }: DailyAppointmentsChartProps) {
  return (
    <BaseChart 
      title="Daily Appointments" 
      description="Trend of scheduled appointments per day" 
      data={data as unknown as Record<string, unknown>[]}
    >
      <BarChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <ChartGrid />
        <ChartXAxis dataKey="day" />
        <ChartYAxis />
        <ChartTooltip />
        <Bar 
          dataKey="count" 
          name="Appointments" 
          fill="hsl(var(--chart-1))" 
          radius={[4, 4, 0, 0]} 
        />
      </BarChart>
    </BaseChart>
  );
}
