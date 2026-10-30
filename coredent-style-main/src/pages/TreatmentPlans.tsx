// ============================================
// CoreDent PMS - Treatment Plans Page
// Manage treatment plans for patients
// ============================================

import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { AlertTriangle, Plus, Search, FileText } from 'lucide-react';
import { TreatmentPlanCard } from '@/components/treatment/TreatmentPlanCard';
import { TreatmentPlanDialog } from '@/components/treatment/TreatmentPlanDialog';
import { TreatmentPlanDetails } from '@/components/treatment/TreatmentPlanDetails';
import { TreatmentPlanVisualBuilder } from '@/components/treatment/TreatmentPlanVisualBuilder';
import { treatmentPlanApi } from '@/services/treatmentPlanApi';
import { patientsApi } from '@/services/api';
import { schedulingApi } from '@/services/schedulingApi';
import type {
  TreatmentPlan,
  TreatmentPlanCreateInput,
  TreatmentPlanUpdateInput,
  TreatmentProcedureCreateInput,
} from '@/types/treatmentPlan';

type TabFilter = 'all' | 'active' | 'completed';

export default function TreatmentPlans() {
  const { toast } = useToast();
  const { role } = useAuth();
  const canModifyTreatment = role === 'owner' || role === 'dentist';
  const canDeleteTreatment = role === 'owner' || role === 'admin';
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<TabFilter>('all');
  const [isPlanDialogOpen, setIsPlanDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<TreatmentPlan | null>(null);
  const [viewingPlan, setViewingPlan] = useState<TreatmentPlan | null>(null);
  const [deletingPlan, setDeletingPlan] = useState<TreatmentPlan | null>(null);
  const [isVisualBuilderOpen, setIsVisualBuilderOpen] = useState(false);

  const { data: rawPlans = [], isLoading, isError } = useQuery({
    queryKey: ['treatment-plans'],
    queryFn: () => treatmentPlanApi.getPlans(),
    staleTime: 5 * 60 * 1000,
  });
  const { data: patientsResponse } = useQuery({
    queryKey: ['patients', 'treatment-plan-options'],
    queryFn: () => patientsApi.list({ status: 'active', limit: 100 }),
  });
  const { data: providers = [] } = useQuery({
    queryKey: ['providers', 'treatment-plan-options'],
    queryFn: () => schedulingApi.getProviders(),
  });

  const plans = useMemo(() => {
    const patientNames = new Map(
      (patientsResponse?.data?.data ?? []).map((patient) => [
        patient.id,
        `${patient.firstName} ${patient.lastName}`.trim(),
      ]),
    );
    const providerNames = new Map(
      providers.map((provider) => [provider.id, provider.name]),
    );
    return rawPlans.map((plan) => ({
      ...plan,
      patientName: plan.patientName ?? patientNames.get(plan.patientId),
      providerName: plan.providerName ?? providerNames.get(plan.providerId),
    }));
  }, [patientsResponse, providers, rawPlans]);

  const filteredPlans = plans.filter((plan) => {
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      plan.title.toLowerCase().includes(query) ||
      (plan.patientName?.toLowerCase().includes(query) ?? false) ||
      (plan.providerName?.toLowerCase().includes(query) ?? false);
    let matchesTab = true;
    if (activeTab === 'active') {
      matchesTab = ['draft', 'presented', 'accepted', 'partially_accepted', 'in_progress'].includes(plan.status);
    } else if (activeTab === 'completed') {
      matchesTab = plan.status === 'completed';
    }
    return matchesSearch && matchesTab;
  });

  const replacePlan = (updated: TreatmentPlan) => {
    queryClient.setQueryData(['treatment-plans'], (previous: TreatmentPlan[] | undefined) =>
      previous?.map((plan) => (plan.id === updated.id ? updated : plan)),
    );
  };

  const loadPlanDetails = async (plan: TreatmentPlan): Promise<TreatmentPlan> =>
    treatmentPlanApi.getPlan(plan.id, {
      patientName: plan.patientName,
      providerName: plan.providerName,
    });

  const handleCreatePlan = async (data: TreatmentPlanCreateInput): Promise<boolean> => {
    try {
      const newPlan = await treatmentPlanApi.createPlan({ ...data, status: 'draft' });
      queryClient.setQueryData(['treatment-plans'], (previous: TreatmentPlan[] | undefined) =>
        previous ? [newPlan, ...previous] : [newPlan],
      );
      toast({ title: 'Plan created', description: `Treatment plan "${data.title}" has been created` });
      setEditingPlan(newPlan);
      setIsVisualBuilderOpen(true);
      return true;
    } catch {
      toast({ title: 'Error', description: 'Failed to create treatment plan', variant: 'destructive' });
      return false;
    }
  };

  const handleUpdatePlan = async (data: TreatmentPlanUpdateInput) => {
    if (!editingPlan) return;
    try {
      const base = await treatmentPlanApi.updatePlan(editingPlan.id, data, {
        patientName: editingPlan.patientName,
        providerName: editingPlan.providerName,
      });
      const updated = {
        ...base,
        procedures: editingPlan.procedures,
        phases: editingPlan.phases,
        proceduresLoaded: editingPlan.proceduresLoaded,
      };
      replacePlan(updated);
      if (viewingPlan?.id === updated.id) setViewingPlan(updated);
      setEditingPlan(null);
      toast({ title: 'Plan updated', description: 'Treatment plan has been updated' });
    } catch {
      toast({ title: 'Error', description: 'Failed to update treatment plan', variant: 'destructive' });
    }
  };

  const handleCancelPlan = async () => {
    if (!deletingPlan) return;
    try {
      await treatmentPlanApi.deletePlan(deletingPlan.id);
      const cancelledPlan: TreatmentPlan = { ...deletingPlan, status: 'cancelled' };
      replacePlan(cancelledPlan);
      if (viewingPlan?.id === deletingPlan.id) setViewingPlan(cancelledPlan);
      setDeletingPlan(null);
      toast({ title: 'Plan cancelled', description: 'Treatment plan status has been set to cancelled' });
    } catch {
      toast({ title: 'Error', description: 'Failed to cancel treatment plan', variant: 'destructive' });
    }
  };

  const handleViewPlan = async (plan: TreatmentPlan) => {
    try {
      const detailedPlan = await loadPlanDetails(plan);
      setViewingPlan(detailedPlan);
      replacePlan(detailedPlan);
    } catch {
      toast({ title: 'Error', description: 'Failed to load treatment-plan details', variant: 'destructive' });
    }
  };

  const refreshViewingPlan = async () => {
    if (!viewingPlan) return;
    const refreshed = await loadPlanDetails(viewingPlan);
    setViewingPlan(refreshed);
    replacePlan(refreshed);
  };

  const handleAddProcedure = async (data: TreatmentProcedureCreateInput) => {
    if (!viewingPlan) return;
    try {
      await treatmentPlanApi.addProcedure(viewingPlan.id, data);
      await refreshViewingPlan();
      toast({ title: 'Procedure added', description: `${data.description} added to treatment plan` });
    } catch {
      toast({ title: 'Error', description: 'Failed to add procedure', variant: 'destructive' });
      throw new Error('Failed to add procedure');
    }
  };

  const handleCompleteProcedure = async (procedureId: string) => {
    try {
      await treatmentPlanApi.completeProcedure(procedureId);
      await refreshViewingPlan();
      toast({ title: 'Procedure completed', description: 'Procedure has been marked as completed' });
    } catch {
      toast({ title: 'Error', description: 'Failed to complete procedure', variant: 'destructive' });
    }
  };

  const handleDeleteProcedure = async (procedureId: string) => {
    try {
      await treatmentPlanApi.deleteProcedure(procedureId);
      await refreshViewingPlan();
      toast({ title: 'Procedure removed', description: 'Procedure has been removed from the plan' });
    } catch {
      toast({ title: 'Error', description: 'Failed to remove procedure', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Treatment Plans</h1>
          <p className="text-muted-foreground">Create and manage patient treatment plans</p>
        </div>
        {canModifyTreatment && (
          <Button onClick={() => setIsPlanDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" /> New Plan
          </Button>
        )}
      </div>

      {isError && (
        <Alert variant="destructive" role="alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Treatment plans unavailable</AlertTitle>
          <AlertDescription>Treatment-plan data could not be loaded. An empty plan list is not being assumed.</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search plans…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} className="pl-9" />
        </div>
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as TabFilter)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="completed">Completed</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((value) => <Skeleton key={value} className="h-[280px] rounded-xl" />)}
        </div>
      ) : filteredPlans.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No treatment plans found</h3>
          <p className="text-muted-foreground mt-1">{searchQuery ? 'Try adjusting your search terms' : 'Create a new treatment plan to get started'}</p>
          {!searchQuery && canModifyTreatment && (
            <Button className="mt-4" onClick={() => setIsPlanDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> Create Plan
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredPlans.map((plan) => (
            <TreatmentPlanCard
              key={plan.id}
              plan={plan}
              onView={handleViewPlan}
              onEdit={setEditingPlan}
              onDelete={setDeletingPlan}
              canEdit={canModifyTreatment}
              canCancel={canDeleteTreatment}
            />
          ))}
        </div>
      )}

      <TreatmentPlanDialog open={isPlanDialogOpen} onOpenChange={setIsPlanDialogOpen} onSubmit={handleCreatePlan} />

      <AlertDialog
        open={isVisualBuilderOpen || !!editingPlan}
        onOpenChange={(open) => {
          if (!open) {
            setIsVisualBuilderOpen(false);
            setEditingPlan(null);
          }
        }}
      >
        <AlertDialogContent className="max-w-[95vw] w-[1400px] h-[90vh]">
          <AlertDialogHeader>
            <AlertDialogTitle>Treatment Plan Designer</AlertDialogTitle>
            <AlertDialogDescription>Update the plan fields supported by the treatment API.</AlertDialogDescription>
          </AlertDialogHeader>
          {editingPlan && (
            <TreatmentPlanVisualBuilder
              plan={editingPlan}
              onUpdate={handleUpdatePlan}
              onCancel={() => {
                setIsVisualBuilderOpen(false);
                setEditingPlan(null);
              }}
            />
          )}
        </AlertDialogContent>
      </AlertDialog>

      <TreatmentPlanDetails
        open={!!viewingPlan}
        onOpenChange={(open) => !open && setViewingPlan(null)}
        plan={viewingPlan}
        onAddProcedure={handleAddProcedure}
        onCompleteProcedure={handleCompleteProcedure}
        onDeleteProcedure={handleDeleteProcedure}
        canModify={canModifyTreatment}
        canDelete={canDeleteTreatment}
      />

      <AlertDialog open={!!deletingPlan} onOpenChange={(open) => !open && setDeletingPlan(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Treatment Plan?</AlertDialogTitle>
            <AlertDialogDescription>
              This sets the treatment plan "{deletingPlan?.title}" to cancelled. The plan remains in the clinical record.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Plan</AlertDialogCancel>
            <AlertDialogAction onClick={handleCancelPlan} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Cancel Plan
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
