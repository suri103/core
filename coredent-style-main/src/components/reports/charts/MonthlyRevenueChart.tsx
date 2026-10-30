import {
  BarChart, 
  Bar, 
  Legend 
} from 'recharts';
import { 
  BaseChart, 
  ChartGrid, 
  ChartXAxis, 
  ChartYAxis, 
  ChartTooltip 
} from './BaseChart';
import type { RevenueMonthMetric } from '@/types/reports';

interface MonthlyRevenueChartProps {
  data: RevenueMonthMetric[];
  formatCurrency: (amount: number) => string;
}

export function MonthlyRevenueChart({ data, formatCurrency }: MonthlyRevenueChartProps) {
  return (
    <BaseChart 
      title="Monthly Billing Breakdown" 
      description="Comparing revenue generation and collections side by side" 
      data={data as unknown as Record<string, unknown>[]}
    >
      <BarChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <ChartGrid />
        <ChartXAxis dataKey="month" />
        <ChartYAxis formatter={formatCurrency} />
        <ChartTooltip formatter={formatCurrency} />
        <Legend verticalAlign="top" height={36} />
        <Bar 
          dataKey="revenue" 
          name="Revenue" 
          fill="hsl(var(--chart-1))" 
          radius={[4, 4, 0, 0]} 
        />
        <Bar 
          dataKey="collected" 
          name="Collected" 
          fill="hsl(var(--chart-2))" 
          radius={[4, 4, 0, 0]} 
        />
      </BarChart>
    </BaseChart>
  );
}
