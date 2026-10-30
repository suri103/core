// ============================================
// Platform console tab panels (overview, clinics, users, subs, security)
// ============================================

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { TabsContent } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Building2, Users, DollarSign, AlertTriangle, Search, ShieldCheck, Activity,
} from 'lucide-react';
import type {
  PlatformMetrics, PlatformClinic, PlatformUser, PlatformSubscription, PlatformAuditEvent,
} from '@/services/platformApi';
import { ClinicsTable } from './ClinicsTable';
import { UsersTable } from './UsersTable';
import { SubscriptionsTable } from './SubscriptionsTable';

function formatMoney(value: number | string | null | undefined): string {
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (n == null || Number.isNaN(n)) return '$0';
  return n.toLocaleString('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0,
  });
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

interface PlatformTabsProps {
  metrics: PlatformMetrics | null;
  metricsError: string | null;
  isLoadingMetrics: boolean;
  clinics: PlatformClinic[];
  isLoadingClinics: boolean;
  onToggleClinic: (clinic: PlatformClinic) => void;
  users: PlatformUser[];
  isLoadingUsers: boolean;
  onToggleUser?: (user: PlatformUser) => void;
  subs: PlatformSubscription[];
  isLoadingSubs: boolean;
  events: PlatformAuditEvent[];
  isLoadingEvents: boolean;
  search: string;
  onSearchChange: (v: string) => void;
}

export function PlatformTabs(props: PlatformTabsProps) {
  const {
    metrics, metricsError, isLoadingMetrics,
    clinics, isLoadingClinics, onToggleClinic,
    users, isLoadingUsers, onToggleUser,
    subs, isLoadingSubs,
    events, isLoadingEvents,
    search, onSearchChange,
  } = props;

  const statCards = useMemo(() => {
    if (!metrics) return [];
    return [
      { title: 'Total Clinics', value: metrics.total_clinics, icon: Building2,
        sub: `${metrics.active_clinics} active · ${metrics.suspended_clinics} suspended` },
      { title: 'Total Users', value: metrics.total_users, icon: Users,
        sub: `${metrics.active_users} active` },
      { title: 'MRR', value: formatMoney(metrics.mrr), icon: DollarSign,
        sub: `${metrics.active_subscriptions} active subscriptions` },
      { title: 'Failed Payments', value: metrics.failed_payment_clinics, icon: AlertTriangle,
        sub: `${metrics.past_due_subscriptions} past due` },
    ];
  }, [metrics]);

  return (
    <>
      {/* ---------- Overview ---------- */}
      <TabsContent value="overview" className="mt-6 space-y-6">
        {isLoadingMetrics ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          </div>
        ) : metricsError ? (
          <Card><CardContent className="pt-6 text-destructive">{metricsError}</CardContent></Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {statCards.map((s) => {
              const Icon = s.icon;
              return (
                <Card key={s.title}>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">{s.title}</CardTitle>
                    <Icon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{s.value}</div>
                    <p className="text-xs text-muted-foreground">{s.sub}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4" /> Growth
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <Row label="New registrations this month" value={metrics?.new_registrations_this_month ?? '—'} />
              <Row label="Cancellations this month" value={metrics?.canceled_this_month ?? '—'} />
              <Row label="Churn rate" value={metrics ? `${metrics.churn_rate_percent}%` : '—'} />
              <Row label="Trials running" value={metrics?.trialing_subscriptions ?? '—'} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" /> Billing health
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <Row label="Active subscriptions" value={metrics?.active_subscriptions ?? '—'} />
              <Row label="Past due (dunning)" value={metrics?.past_due_subscriptions ?? '—'} />
              <Row label="Monthly recurring revenue" value={metrics ? formatMoney(metrics.mrr) : '—'} />
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      {/* ---------- Clinics ---------- */}
      <TabsContent value="clinics" className="mt-6 space-y-4">
        <div className="flex items-center gap-2 max-w-sm">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search clinics by name, email or slug..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <ClinicsTable clinics={clinics} isLoading={isLoadingClinics} onToggle={onToggleClinic} />
      </TabsContent>

      {/* ---------- Users ---------- */}
      <TabsContent value="users" className="mt-6 space-y-4">
        <div className="flex items-center gap-2 max-w-sm">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search users by name or email..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <UsersTable users={users} isLoading={isLoadingUsers} onToggleUser={onToggleUser} />
      </TabsContent>

      {/* ---------- Subscriptions ---------- */}
      <TabsContent value="subscriptions" className="mt-6">
        <SubscriptionsTable subs={subs} isLoading={isLoadingSubs} />
      </TabsContent>

      {/* ---------- Security ---------- */}
      <TabsContent value="security" className="mt-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" /> Recent audit events (platform-wide)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingEvents ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}
              </div>
            ) : events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No audit events yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>IP</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((ev) => (
                    <TableRow key={ev.id}>
                      <TableCell className="text-xs">{new Date(ev.created_at).toLocaleString()}</TableCell>
                      <TableCell><Badge variant="outline">{ev.action}</Badge></TableCell>
                      <TableCell className="text-xs">{ev.entity_type}</TableCell>
                      <TableCell className="text-xs">{ev.actor_email ?? 'system'}</TableCell>
                      <TableCell className="text-xs">{ev.ip_address ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </TabsContent>
    </>
  );
}
