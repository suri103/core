import {
  AreaChart, 
  Area, 
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

interface RevenueChartProps {
  data: RevenueMonthMetric[];
  formatCurrency: (amount: number) => string;
}

export function RevenueChart({ data, formatCurrency }: RevenueChartProps) {
  return (
    <BaseChart 
      title="Revenue Overview" 
      description="Comparing monthly total revenue against collections" 
      data={data as unknown as Record<string, unknown>[]}
    >
      <AreaChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.3}/>
            <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0}/>
          </linearGradient>
          <linearGradient id="colorCollected" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3}/>
            <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <ChartGrid />
        <ChartXAxis dataKey="month" />
        <ChartYAxis formatter={formatCurrency} />
        <ChartTooltip formatter={formatCurrency} />
        <Legend verticalAlign="top" height={36} />
        <Area 
          type="monotone" 
          dataKey="revenue" 
          name="Revenue" 
          stroke="hsl(var(--chart-1))" 
          fillOpacity={1} 
          fill="url(#colorRevenue)" 
          strokeWidth={2}
        />
        <Area 
          type="monotone" 
          dataKey="collected" 
          name="Collected" 
          stroke="hsl(var(--chart-2))" 
          fillOpacity={1} 
          fill="url(#colorCollected)" 
          strokeWidth={2}
        />
      </AreaChart>
    </BaseChart>
  );
}
