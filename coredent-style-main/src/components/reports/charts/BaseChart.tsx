import React, { ReactNode } from 'react';
import { 
  ResponsiveContainer, 
  CartesianGrid, 
  XAxis, 
  YAxis, 
  Tooltip 
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface BaseChartProps {
  title: string;
  description?: string;
  data: Record<string, unknown>[];
  children: ReactNode;
  height?: number | string;
}

export const BaseChart = React.memo(({ 
  title, 
  description, 
  data, 
  children, 
  height = 300
}: BaseChartProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            {/* The actual chart (BarChart, LineChart, AreaChart) will be passed as children */}
            {React.cloneElement(children as React.ReactElement, { data })}
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
});

BaseChart.displayName = 'BaseChart';

// Shared chart components to reduce duplication in individual chart files
export const ChartGrid = () => <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />;
export const ChartXAxis = ({ dataKey }: { dataKey: string }) => <XAxis dataKey={dataKey} className="text-xs" />;
export const ChartYAxis = ({ formatter }: { formatter?: (v: number) => string }) => (
  <YAxis className="text-xs" tickFormatter={formatter} />
);
export const ChartTooltip = ({ formatter }: { formatter?: (v: number) => string }) => (
  <Tooltip
    formatter={formatter}
    contentStyle={{
      backgroundColor: 'hsl(var(--background))',
      border: '1px solid hsl(var(--border))',
      borderRadius: '8px',
    }}
  />
);
