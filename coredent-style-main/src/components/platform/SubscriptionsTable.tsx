// ============================================
// Platform console — SaaS subscription directory table
// ============================================

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { BadgeProps } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import type { PlatformSubscription } from '@/services/platformApi';

interface SubscriptionsTableProps {
  subs: PlatformSubscription[];
  isLoading: boolean;
}

const STATUS_VARIANT: Record<string, NonNullable<BadgeProps['variant']>> = {
  active: 'default',
  trialing: 'secondary',
  past_due: 'destructive',
  canceled: 'outline',
  paused: 'outline',
  expired: 'outline',
  unpaid: 'destructive',
  incomplete: 'outline',
};

export function SubscriptionsTable({ subs, isLoading }: SubscriptionsTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12" />)}
      </div>
    );
  }
  if (subs.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          No clinic subscriptions found.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Plan</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Interval</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Period ends</TableHead>
              <TableHead>Canceled at</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {subs.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-medium">{s.plan_name ?? '—'}</TableCell>
                <TableCell>{s.plan_amount != null ? `$${s.plan_amount}` : '—'}</TableCell>
                <TableCell>{s.interval ?? '—'}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[s.status] ?? 'outline'}>
                    {s.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs">
                  {s.current_period_end
                    ? new Date(s.current_period_end).toLocaleDateString()
                    : '—'}
                </TableCell>
                <TableCell className="text-xs">
                  {s.canceled_at ? new Date(s.canceled_at).toLocaleDateString() : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
