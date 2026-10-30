import {
  PieChart, 
  Pie, 
  Cell, 
  Legend, 
  Tooltip 
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import type { AppointmentTypeMetric } from '@/types/reports';

interface AppointmentPieChartProps {
  data: AppointmentTypeMetric[];
  colors: string[];
}

export function AppointmentPieChart({ data, colors }: AppointmentPieChartProps) {
  const chartData = data.map(item => ({
    name: item.type,
    value: item.count
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Appointment Distribution</CardTitle>
        <CardDescription>Breakdown by appointment type</CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ height: 300 }} className="flex justify-center items-center">
          <PieChart width={400} height={300}>
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <Legend verticalAlign="bottom" height={36} />
            <Pie
              data={chartData}
              cx="50%"
              cy="45%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={4}
              dataKey="value"
            >
              {chartData.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
              ))}
            </Pie>
          </PieChart>
        </div>
      </CardContent>
    </Card>
  );
}
