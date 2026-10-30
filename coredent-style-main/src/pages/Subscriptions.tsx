import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { formatCurrency as formatCurrencyUtil } from '@/lib/utils';
import {
  useSubscriptionPlans,
  useSubscriptions,
  useSubscriptionStats,
  useCreateSubscription,
  useCancelSubscription,
} from '@/hooks/useSubscriptions';
import type { SubscriptionPlan, Subscription } from '@/services/subscriptionsApi';
import { format } from 'date-fns';
import { useQueryClient } from '@tanstack/react-query';
import {
  CreditCard,
  TrendingUp,
  Users,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  PauseCircle,
  ArrowUpRight,
  DollarSign,
  Package,
  FileText,
} from 'lucide-react';

// ==================== Utility Functions ====================

// Platform (CoreDent) subscription pricing is always billed in USD; route
// through the shared money-formatting util so currency stays a parameter.
const formatCurrency = (amount: number | string) => {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return formatCurrencyUtil(num, 'USD');
};

const formatInterval = (interval: string) => {
  const map: Record<string, string> = {
    weekly: '/week',
    monthly: '/month',
    quarterly: '/quarter',
    semi_annual: '/6 months',
    annual: '/year',
  };
  return map[interval] || '';
};

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  trialing: { label: 'Trial', color: 'bg-blue-100 text-blue-800', icon: <Clock className="h-3 w-3" /> },
  active: { label: 'Active', color: 'bg-green-100 text-green-800', icon: <CheckCircle2 className="h-3 w-3" /> },
  past_due: { label: 'Past Due', color: 'bg-red-100 text-red-800', icon: <AlertTriangle className="h-3 w-3" /> },
  canceled: { label: 'Canceled', color: 'bg-gray-100 text-gray-800', icon: <XCircle className="h-3 w-3" /> },
  paused: { label: 'Paused', color: 'bg-yellow-100 text-yellow-800', icon: <PauseCircle className="h-3 w-3" /> },
  incomplete: { label: 'Incomplete', color: 'bg-orange-100 text-orange-800', icon: <Clock className="h-3 w-3" /> },
};

// ==================== Plan Card Component ====================

function PlanCard({ plan, onSelect, isCurrent }: { plan: SubscriptionPlan; onSelect: (plan: SubscriptionPlan) => void; isCurrent?: boolean }) {
  return (
    <Card className={`relative flex flex-col ${isCurrent ? 'border-primary ring-2 ring-primary' : ''}`}>
      {isCurrent && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <Badge variant="default" className="bg-primary">Current</Badge>
        </div>
      )}
      <CardHeader>
        <CardTitle>{plan.name}</CardTitle>
        <CardDescription>{plan.description || plan.short_description || ''}</CardDescription>
        <div className="mt-2">
          <span className="text-3xl font-bold">{formatCurrency(plan.amount)}</span>
          <span className="text-muted-foreground ml-1">{formatInterval(plan.interval)}</span>
        </div>
        {plan.trial_period_days > 0 && (
          <Badge variant="outline" className="mt-2 w-fit">
            {plan.trial_period_days}-day free trial
          </Badge>
        )}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {plan.features && plan.features.length > 0 && (
          <ul className="space-y-2 text-sm">
            {plan.features.map((feature, i) => (
              <li key={i} className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 mt-0.5 text-green-500 shrink-0" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          onClick={() => onSelect(plan)}
          disabled={isCurrent}
        >
          {isCurrent ? 'Current Plan' : 'Subscribe'}
        </Button>
      </CardFooter>
    </Card>
  );
}

// ==================== Stats Component ====================

function StatsCards({ stats }: { stats: Record<string, number> | null }) {
  if (!stats) return null;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Active Subscriptions</CardTitle>
          <Users className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{String(stats.total_active || 0)}</div>
          <p className="text-xs text-muted-foreground">{String(stats.total_trials || 0)} in trial</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Monthly Revenue (MRR)</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatCurrency(stats.mrr || 0)}</div>
          <p className="text-xs text-muted-foreground">
            {Number(stats.mrr_growth_percent || 0) > 0 ? (
              <span className="text-green-500 flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3" />
                {Number(stats.mrr_growth_percent).toFixed(1)}%
              </span>
            ) : 'No growth'}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Past Due</CardTitle>
          <AlertTriangle className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-amber-600">{String(stats.total_past_due || 0)}</div>
          <p className="text-xs text-muted-foreground">Needs attention</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Churn Rate</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${(stats.churn_rate || 0) > 10 ? 'text-red-600' : 'text-green-600'}`}>
            {Number(stats.churn_rate || 0).toFixed(1)}%
          </div>
          <p className="text-xs text-muted-foreground">{String(stats.total_canceled_this_month || 0)} canceled this month</p>
        </CardContent>
      </Card>
    </div>
  );
}

// ==================== Main Page Component ====================

const Subscriptions = () => {
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
  const [showSubscribeDialog, setShowSubscribeDialog] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelAtPeriodEnd, setCancelAtPeriodEnd] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Queries
  const { data: plansResponse, isLoading: plansLoading } = useSubscriptionPlans();
  const { data: subsResponse, isLoading: subsLoading } = useSubscriptions();
  const { data: statsData } = useSubscriptionStats();

  // Mutations
  const createSubscriptionMutation = useCreateSubscription();
  const cancelSubscriptionMutation = useCancelSubscription();

  // Extract data from API responses
  const plans = (plansResponse && Array.isArray(plansResponse)) ? plansResponse : [];
  const subscriptions: Subscription[] = subsResponse
    ? (Array.isArray(subsResponse) ? subsResponse : ((subsResponse as { subscriptions?: Subscription[] })?.subscriptions || []))
    : [];
  const activeSubscription = subscriptions.find(
    (s: Subscription) => s.status === 'active' || s.status === 'trialing' || s.status === 'past_due'
  );

  // Extract stats
  const stats = (statsData && typeof statsData === 'object' && !('success' in statsData))
    ? (statsData as Record<string, number>)
    : null;

  if (plansLoading || subsLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const handleSelectPlan = (plan: SubscriptionPlan) => {
    setSelectedPlan(plan);
    setShowSubscribeDialog(true);
  };

  const handleSubscribe = async () => {
    if (!selectedPlan) return;
    setIsSubmitting(true);
    try {
      await createSubscriptionMutation.mutateAsync({
        plan_id: selectedPlan.id,
        trial_period_days: selectedPlan.trial_period_days || undefined,
      });
      toast({
        title: 'Subscription Created',
        description: `Successfully subscribed to ${selectedPlan.name}. ${selectedPlan.trial_period_days > 0 ? `Your ${selectedPlan.trial_period_days}-day free trial has started.` : ''}`,
      });
      setShowSubscribeDialog(false);
      setSelectedPlan(null);
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    } catch (error: any) {
      toast({
        title: 'Subscription Failed',
        description: error?.response?.data?.detail || 'Failed to create subscription. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!activeSubscription) return;
    setIsSubmitting(true);
    try {
      await cancelSubscriptionMutation.mutateAsync({
        id: activeSubscription.id,
        data: {
          cancel_at_period_end: cancelAtPeriodEnd,
          reason: cancelReason || undefined,
        },
      });
      toast({
        title: 'Subscription Canceled',
        description: cancelAtPeriodEnd
          ? 'Your subscription will be canceled at the end of the current billing period.'
          : 'Your subscription has been canceled.',
      });
      setShowCancelDialog(false);
      setCancelReason('');
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    } catch (error: any) {
      toast({
        title: 'Cancellation Failed',
        description: error?.response?.data?.detail || 'Failed to cancel subscription. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Subscriptions & Billing</h1>
        <p className="text-muted-foreground mt-1">Manage your subscription plan and billing preferences</p>
      </div>

      <StatsCards stats={stats} />

      {activeSubscription && (
        <Alert variant={activeSubscription.status === 'past_due' ? 'destructive' : 'default'}>
          {statusConfig[activeSubscription.status]?.icon || <CreditCard className="h-4 w-4" />}
          <AlertTitle>
            {activeSubscription.status === 'past_due' ? 'Payment Action Required' : 'Active Subscription'}
          </AlertTitle>
          <AlertDescription>
            {activeSubscription.status === 'past_due'
              ? `Your last payment failed: ${activeSubscription.last_payment_error || 'Unknown error'}`
              : `Current billing period ends ${activeSubscription.current_period_end ? format(new Date(activeSubscription.current_period_end), 'MMM dd, yyyy') : 'N/A'}`}
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="plans" className="space-y-4">
        <TabsList>
          <TabsTrigger value="plans">
            <CreditCard className="h-4 w-4 mr-2" />
            Available Plans
          </TabsTrigger>
          <TabsTrigger value="current">
            <FileText className="h-4 w-4 mr-2" />
            My Subscription
          </TabsTrigger>
        </TabsList>

        {/* Available Plans Tab */}
        <TabsContent value="plans" className="space-y-4">
          {plans.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan: SubscriptionPlan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  onSelect={handleSelectPlan}
                  isCurrent={activeSubscription?.plan_id === plan.id}
                />
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Package className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Plans Available</h3>
                <p className="text-muted-foreground text-center">
                  Contact your administrator to set up subscription plans
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* My Subscription Tab */}
        <TabsContent value="current" className="space-y-4">
          {activeSubscription ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Current Subscription</CardTitle>
                    <CardDescription>Your subscription details and management</CardDescription>
                  </div>
                  <Badge className={statusConfig[activeSubscription.status]?.color}>
                    {statusConfig[activeSubscription.status]?.label || activeSubscription.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Plan ID</Label>
                    <p className="text-sm font-mono truncate mt-1">{activeSubscription.plan_id}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Next Billing Date</Label>
                    <p className="text-sm mt-1">
                      {activeSubscription.next_billing_date
                        ? format(new Date(activeSubscription.next_billing_date), 'MMM dd, yyyy')
                        : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Payment Error</Label>
                    <p className="text-sm mt-1 text-red-600">
                      {activeSubscription.last_payment_error || 'None'}
                    </p>
                  </div>
                </div>

                {activeSubscription.cancel_at_period_end && (
                  <Alert>
                    <Clock className="h-4 w-4" />
                    <AlertTitle>Cancellation Scheduled</AlertTitle>
                    <AlertDescription>
                      Your subscription will be canceled at the end of the current billing period.
                    </AlertDescription>
                  </Alert>
                )}

                <Separator />

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setShowCancelDialog(true)}
                    disabled={activeSubscription.cancel_at_period_end}
                  >
                    <XCircle className="h-4 w-4 mr-2" />
                    {activeSubscription.cancel_at_period_end ? 'Cancellation Scheduled' : 'Cancel Subscription'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <CreditCard className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Active Subscription</h3>
                <p className="text-muted-foreground text-center mb-4">
                  Choose a plan from the Available Plans tab to get started
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Subscribe Dialog */}
      <Dialog open={showSubscribeDialog} onOpenChange={setShowSubscribeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Subscription</DialogTitle>
            <DialogDescription>
              You are about to subscribe to <strong>{selectedPlan?.name}</strong> for{' '}
              {formatCurrency(selectedPlan?.amount || 0)}
              {formatInterval(selectedPlan?.interval || '')}.
              {(selectedPlan?.trial_period_days ?? 0) > 0 && (
                <span className="block mt-2 text-green-600 font-medium">
                  You will get a {selectedPlan?.trial_period_days}-day free trial before being charged.
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSubscribeDialog(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleSubscribe} disabled={isSubmitting}>
              {isSubmitting ? 'Processing...' : ((selectedPlan?.trial_period_days ?? 0) > 0 ? 'Start Free Trial' : 'Subscribe Now')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Dialog */}
      <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Subscription</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel your subscription? This action will take effect at the end of your current billing period.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="cancelAtPeriodEnd"
                checked={cancelAtPeriodEnd}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCancelAtPeriodEnd(e.target.checked)}
                className="rounded border-gray-300"
              />
              <Label htmlFor="cancelAtPeriodEnd" className="cursor-pointer">
                Continue until end of billing period
              </Label>
            </div>
            <div>
              <Label htmlFor="cancelReason">Reason for canceling (optional)</Label>
              <Input
                id="cancelReason"
                placeholder="e.g., Too expensive, not using it, etc."
                value={cancelReason}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCancelReason(e.target.value)}
                className="mt-2"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCancelDialog(false)} disabled={isSubmitting}>
              Keep Subscription
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancelSubscription}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Processing...' : 'Cancel Subscription'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Subscriptions;