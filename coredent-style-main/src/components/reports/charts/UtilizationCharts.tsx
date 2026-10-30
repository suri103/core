import {
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { PeakHourMetric, ChairMetric, DayOfWeekMetric } from '@/types/reports';

interface UtilizationChartsProps {
  peakHours: PeakHourMetric[];
  byChair: ChairMetric[];
  byDayOfWeek: DayOfWeekMetric[];
}

export function UtilizationCharts({ peakHours, byChair, byDayOfWeek }: UtilizationChartsProps) {
  const formatPercent = (val: number) => `${val}%`;

  return (
    <Card className="col-span-1 lg:col-span-3">
      <CardHeader>
        <CardTitle>Operatory & Chair Utilization Analysis</CardTitle>
        <CardDescription>
          Detailed analytics of operatory booking efficiency by hour, day, and chair.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="hourly" className="space-y-4">
          <TabsList className="grid w-full sm:w-[400px] grid-cols-3">
            <TabsTrigger value="hourly">Hourly Peak</TabsTrigger>
            <TabsTrigger value="daily">Weekly Trend</TabsTrigger>
            <TabsTrigger value="chairs">Chairs</TabsTrigger>
          </TabsList>

          {/* Hourly Peak */}
          <TabsContent value="hourly" className="pt-2">
            <div style={{ height: 350 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={peakHours} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorUtil" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--chart-3))" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="hsl(var(--chart-3))" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="hour" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={formatPercent} />
                  <Tooltip
                    formatter={formatPercent}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="utilization" 
                    name="Utilization" 
                    stroke="hsl(var(--chart-3))" 
                    fillOpacity={1} 
                    fill="url(#colorUtil)" 
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </TabsContent>

          {/* Weekly Trend */}
          <TabsContent value="daily" className="pt-2">
            <div style={{ height: 350 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byDayOfWeek} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="day" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={formatPercent} />
                  <Tooltip
                    formatter={formatPercent}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar 
                    dataKey="utilization" 
                    name="Avg Utilization" 
                    fill="hsl(var(--chart-4))" 
                    radius={[4, 4, 0, 0]} 
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </TabsContent>

          {/* Chair breakdown */}
          <TabsContent value="chairs" className="pt-2">
            <div style={{ height: 350 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byChair} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="chair" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={formatPercent} />
                  <Tooltip
                    formatter={(val, name) => {
                      if (name === 'utilization') return `${val}%`;
                      return val;
                    }}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar 
                    dataKey="utilization" 
                    name="Utilization" 
                    fill="hsl(var(--chart-5))" 
                    radius={[4, 4, 0, 0]} 
                  />
                  <Bar 
                    dataKey="appointments" 
                    name="Appointments Count" 
                    fill="hsl(var(--chart-2))" 
                    radius={[4, 4, 0, 0]} 
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
