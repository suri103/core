/**
 * DashboardActivityCard Component
 * Displays recent activity on the dashboard
 */

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { ActivityItem } from '@/hooks/useRecentActivity';

interface DashboardActivityCardProps {
  activities: ActivityItem[];
}

/**
 * Activity card component for dashboard
 */
export const DashboardActivityCard = React.memo(function DashboardActivityCard({
  activities,
}: DashboardActivityCardProps) {
  return (
    <Card className="shadow-md border-muted/60">
      <CardHeader className="border-b bg-muted/5 pb-4">
        <CardTitle>Recent Activity</CardTitle>
        <CardDescription>Latest updates from your practice</CardDescription>
      </CardHeader>
      <CardContent className="pt-6">
        <div className="space-y-6">
          {activities.length === 0 ? (
            <div className="text-sm text-muted-foreground">No recent activity</div>
          ) : (
            activities.map((activity) => (
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
  );
});

DashboardActivityCard.displayName = 'DashboardActivityCard';

/**
 * Activity Item Component
 */
function ActivityItem({
  icon: Icon,
  title,
  description,
  time,
}: ActivityItem & { icon: React.ElementType }) {
  return (
    <div className="flex gap-4 group cursor-default">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/5 border border-primary/10 group-hover:bg-primary/10 transition-colors">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="flex-1 space-y-1">
        <p className="text-sm font-bold leading-none">{title}</p>
        <p className="text-sm text-muted-foreground font-medium">{description}</p>
        <p className="text-[10px] text-muted-foreground uppercase font-black tracking-widest mt-1 opacity-60">
          {time}
        </p>
      </div>
    </div>
  );
}
