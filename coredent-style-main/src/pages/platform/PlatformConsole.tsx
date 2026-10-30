// ============================================
// CoreDent SaaS - Platform (Super Admin) Console
// Cross-tenant operations console for the SaaS operator.
// ============================================

import { useState, useCallback, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { useApiRequest } from '@/hooks/useApiRequest';
import { platformApi, suspendClinicNow, reactivateClinicNow, deactivateUserNow, reactivateUserNow } from '@/services/platformApi';
import type { PlatformClinic, PlatformUser } from '@/services/platformApi';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { PlatformTabs } from '@/components/platform/PlatformTabs';

const PAGE_SIZE = 20;

export default function PlatformConsole() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [search, setSearch] = useState('');
  const [confirmTarget, setConfirmTarget] = useState<PlatformClinic | null>(null);
  const [userConfirmTarget, setUserConfirmTarget] = useState<PlatformUser | null>(null);
  const [isToggling, setIsToggling] = useState(false);

  // ---------------- Data fetchers (stable identities) ----------------
  const fetchMetrics = useCallback(() => platformApi.getMetrics(), []);
  const fetchClinics = useCallback(
    () => platformApi.listClinics({ search: search || undefined, limit: PAGE_SIZE }),
    [search],
  );
  const fetchUsers = useCallback(
    () => platformApi.listUsers({ search: search || undefined, limit: PAGE_SIZE }),
    [search],
  );
  const fetchSubs = useCallback(() => platformApi.listSubscriptions({ limit: PAGE_SIZE }), []);
  const fetchEvents = useCallback(() => platformApi.listAuditEvents({ limit: 30 }), []);

  const { data: metrics, isLoading: isLoadingMetrics, error: metricsError, execute: loadMetrics } =
    useApiRequest(fetchMetrics, { errorMessage: 'Failed to load platform metrics' });
  const { data: clinicsPage, isLoading: isLoadingClinics, execute: loadClinics } = useApiRequest(
    fetchClinics, { errorMessage: 'Failed to load clinics' },
  );
  const { data: usersPage, isLoading: isLoadingUsers, execute: loadUsers } = useApiRequest(
    fetchUsers, { errorMessage: 'Failed to load users' },
  );
  const { data: subsPage, isLoading: isLoadingSubs, execute: loadSubs } = useApiRequest(
    fetchSubs, { errorMessage: 'Failed to load subscriptions' },
  );
  const { data: eventsPage, isLoading: isLoadingEvents, execute: loadEvents } = useApiRequest(
    fetchEvents, { errorMessage: 'Failed to load audit events' },
  );

  // Load per active tab (search debounced)
  useEffect(() => {
    const t = setTimeout(() => {
      if (activeTab === 'overview' && !metrics) loadMetrics();
      if (activeTab === 'clinics') loadClinics();
      if (activeTab === 'users') loadUsers();
      if (activeTab === 'subscriptions') loadSubs();
      if (activeTab === 'security') loadEvents();
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, search]);

  const handleToggleClinic = async () => {
    if (!confirmTarget) return;
    setIsToggling(true);
    try {
      if (confirmTarget.is_active) {
        await suspendClinicNow(confirmTarget.id, 'Suspended from platform console');
        toast({ title: 'Clinic suspended', description: confirmTarget.name });
      } else {
        await reactivateClinicNow(confirmTarget.id);
        toast({ title: 'Clinic reactivated', description: confirmTarget.name });
      }
      setConfirmTarget(null);
      loadClinics();
      loadMetrics();
    } catch (err) {
      toast({
        title: 'Action failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setIsToggling(false);
    }
  };

  const handleToggleUser = async () => {
    if (!userConfirmTarget) return;
    setIsToggling(true);
    try {
      if (userConfirmTarget.is_active) {
        await deactivateUserNow(userConfirmTarget.id, 'Deactivated from platform console');
        toast({ title: 'User deactivated', description: userConfirmTarget.email });
      } else {
        await reactivateUserNow(userConfirmTarget.id);
        toast({ title: 'User reactivated', description: userConfirmTarget.email });
      }
      setUserConfirmTarget(null);
      loadUsers();
      loadMetrics();
    } catch (err) {
      toast({
        title: 'Action failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Platform Console</h1>
        <p className="text-muted-foreground">
          Cross-tenant SaaS operations â€” clinics, subscriptions, users and security events.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="clinics">Clinics</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>

        <PlatformTabs
          metrics={metrics}
          metricsError={metricsError}
          isLoadingMetrics={isLoadingMetrics}
          clinics={clinicsPage?.clinics ?? []}
          isLoadingClinics={isLoadingClinics}
          onToggleClinic={setConfirmTarget}
          users={usersPage?.users ?? []}
          isLoadingUsers={isLoadingUsers}
          onToggleUser={setUserConfirmTarget}
          subs={subsPage?.subscriptions ?? []}
          isLoadingSubs={isLoadingSubs}
          events={eventsPage?.events ?? []}
          isLoadingEvents={isLoadingEvents}
          search={search}
          onSearchChange={setSearch}
        />
      </Tabs>

      {/* Suspend / reactivate confirm */}
      <AlertDialog open={!!confirmTarget} onOpenChange={(open) => !open && setConfirmTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmTarget?.is_active ? 'Suspend' : 'Reactivate'} clinic &quot;{confirmTarget?.name}&quot;?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmTarget?.is_active
                ? 'All users of this clinic will be blocked from logging in. No data is deleted; this is reversible.'
                : 'Clinic users will be able to log in again.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isToggling}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleToggleClinic} disabled={isToggling}>
              {isToggling ? 'Working...' : 'Confirm'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Deactivate / reactivate user confirm */}
      <AlertDialog open={!!userConfirmTarget} onOpenChange={(open) => !open && setUserConfirmTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {userConfirmTarget?.is_active ? 'Deactivate' : 'Reactivate'} user?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {userConfirmTarget?.is_active
                ? 'This user will be blocked from logging in. No data is deleted; this is reversible.'
                : 'This user will be able to log in again.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isToggling}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleToggleUser} disabled={isToggling}>
              {isToggling ? 'Working...' : 'Confirm'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
