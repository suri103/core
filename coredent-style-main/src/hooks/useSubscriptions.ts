import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { subscriptionApi, subscriptionPlanApi } from '@/services/subscriptionsApi';
import { toast } from '@/hooks/use-toast';

// ==================== Query Keys ====================

export const subscriptionKeys = {
  all: ['subscriptions'] as const,
  plans: () => [...subscriptionKeys.all, 'plans'] as const,
  plan: (id: string) => [...subscriptionKeys.plans(), id] as const,
  list: (params?: { status?: string }) => [...subscriptionKeys.all, 'list', params] as const,
  detail: (id: string) => [...subscriptionKeys.all, id] as const,
  usage: (id: string) => [...subscriptionKeys.detail(id), 'usage'] as const,
  dunning: (id: string) => [...subscriptionKeys.detail(id), 'dunning'] as const,
  stats: () => [...subscriptionKeys.all, 'stats'] as const,
  invoices: (id: string) => [...subscriptionKeys.detail(id), 'invoices'] as const,
  trial: (id: string) => [...subscriptionKeys.detail(id), 'trial'] as const,
};

// ==================== Queries ====================

export function useSubscriptionPlans(active_only = true) {
  return useQuery({
    queryKey: subscriptionKeys.plans(),
    queryFn: () => subscriptionPlanApi.list(active_only),
  });
}

export function useSubscriptionPlan(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.plan(id),
    queryFn: () => subscriptionPlanApi.getById(id),
    enabled: enabled && !!id,
  });
}

export function useSubscriptions(params?: { page?: number; limit?: number; status?: string }) {
  return useQuery({
    queryKey: subscriptionKeys.list({ status: params?.status }),
    queryFn: () => subscriptionApi.list(params?.page, params?.limit, params?.status),
  });
}

export function useSubscription(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.detail(id),
    queryFn: () => subscriptionApi.getById(id),
    enabled: enabled && !!id,
  });
}

export function useSubscriptionUsage(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.usage(id),
    queryFn: () => subscriptionApi.getUsage(id),
    enabled: enabled && !!id,
  });
}

export function useDunningEvents(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.dunning(id),
    queryFn: () => subscriptionApi.getDunningEvents(id),
    enabled: enabled && !!id,
  });
}

export function useSubscriptionStats(enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.stats(),
    queryFn: () => subscriptionApi.getStats(),
    enabled,
  });
}

export function useInvoiceHistory(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.invoices(id),
    queryFn: () => subscriptionApi.getInvoiceHistory(id),
    enabled: enabled && !!id,
  });
}

export function useTrial(id: string, enabled = true) {
  return useQuery({
    queryKey: subscriptionKeys.trial(id),
    queryFn: () => subscriptionApi.getTrial(id),
    enabled: enabled && !!id,
  });
}

// ==================== Mutations ====================

export function useCreateSubscription(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.all });
      toast({ title: 'Subscription activated successfully' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to activate subscription',
        description: error.message || 'An error occurred',
      });
    },
  });
}

export function useCancelSubscription(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { cancel_at_period_end?: boolean; reason?: string; feedback?: string } }) =>
      subscriptionApi.cancel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.all });
      toast({ title: 'Subscription cancelled' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to cancel subscription',
        description: error.message || 'An error occurred',
      });
    },
  });
}

export function usePauseSubscription(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { paused_until?: string; reason?: string } }) =>
      subscriptionApi.pause(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.all });
      toast({ title: 'Subscription paused' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to pause subscription',
        description: error.message || 'An error occurred',
      });
    },
  });
}

export function useResumeSubscription(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.all });
      toast({ title: 'Subscription resumed' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to resume subscription',
        description: error.message || 'An error occurred',
      });
    },
  });
}

export function useChangePlan(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { new_plan_id: string; proration_behavior?: string } }) =>
      subscriptionApi.changePlan(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.all });
      toast({ title: 'Plan changed successfully' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to change plan',
        description: error.message || 'An error occurred',
      });
    },
  });
}

export function useRecordUsage(onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { quantity: string; description?: string } }) =>
      subscriptionApi.recordUsage(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: subscriptionKeys.usage(id) });
      toast({ title: 'Usage recorded' });
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to record usage',
        description: error.message || 'An error occurred',
      });
    },
  });
}