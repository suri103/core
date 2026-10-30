/**
 * DashboardStatCard Component
 * Displays a single statistic card on the dashboard
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import React from 'react';

interface DashboardStatCardProps {
  title: string;
  value: string | number;
  icon: React.ElementType;
  description: string;
  trend: string;
  href: string;
}

/**
 * Stat card component for dashboard
 */
export const DashboardStatCard = React.memo(function DashboardStatCard({
  title,
  value,
  icon: Icon,
  description,
  trend,
  href,
}: DashboardStatCardProps) {
  const navigate = useNavigate();

  return (
    <Card
      className="hover:shadow-lg transition-all cursor-pointer group border-muted/60 relative overflow-hidden"
      onClick={() => navigate(href)}
    >
      <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
        <Icon className="h-16 w-16" />
      </div>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground group-hover:text-primary transition-colors">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold tracking-tight">{value}</div>
        <p className="text-xs text-muted-foreground mt-1 font-medium">
          {description}
        </p>
        <div className="flex items-center gap-1 mt-3 px-2 py-0.5 rounded-full bg-primary/5 w-fit text-[10px] text-primary font-bold uppercase tracking-wider">
          <TrendingUp className="h-3 w-3" />
          {trend}
        </div>
      </CardContent>
    </Card>
  );
});

DashboardStatCard.displayName = 'DashboardStatCard';
