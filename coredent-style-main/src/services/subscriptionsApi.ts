import { apiClient } from './api';

// ==================== Types ====================

export interface SubscriptionPlan {
  id: string;
  name: string;
  description: string | null;
  short_description: string | null;
  amount: string;
  currency: string;
  interval: 'weekly' | 'monthly' | 'quarterly' | 'semi_annual' | 'annual';
  trial_period_days: number;
  features: string[] | null;
  limits: Record<string, any> | null;
  is_active: boolean;
  is_recommended: boolean;
  is_usage_based: boolean;
  usage_meter_name: string | null;
  usage_unit_label: string | null;
  included_usage: string;
  overage_rate: string;
  stripe_price_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  practice_id: string;
  patient_id: string | null;
  plan_id: string;
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'paused' | 'expired' | 'incomplete' | 'unpaid';
  interval: string;
  current_period_start: string | null;
  current_period_end: string | null;
  next_billing_date: string | null;
  trial_start: string | null;
  trial_end: string | null;
  trial_used: boolean;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  cancellation_reason: string | null;
  paused_at: string | null;
  paused_until: string | null;
  current_usage: string;
  current_overage: string;
  dunning_retry_count: number;
  last_payment_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface UsageRecord {
  id: string;
  subscription_id: string;
  quantity: string;
  timestamp: string;
  description: string | null;
}

export interface UsageSummary {
  meter_id: string;
  meter_name: string;
  unit_label: string;
  included_quantity: string;
  used_quantity: string;
  overage_quantity: string;
  overage_rate: string;
  overage_cost: string;
}

export interface DunningEvent {
  id: string;
  attempt_number: number;
  action: string;
  result: string | null;
  error_message: string | null;
  scheduled_at: string | null;
  executed_at: string | null;
  created_at: string;
}

export interface SubscriptionStats {
  total_active: number;
  total_trials: number;
  total_past_due: number;
  total_canceled_this_month: number;
  mrr: string;
  mrr_growth_percent: number;
  churn_rate: number;
  trial_conversion_rate: number;
  average_lifetime_days: number;
}

export interface ProrationPreview {
  old_plan: { name: string; amount: number };
  new_plan: { name: string; amount: number };
  days_remaining: number;
  total_days: number;
  proration_amount: number;
  proration_credit: boolean;
  effective_immediately: boolean;
}

export interface TrialResponse {
  subscription_id: string;
  plan_name: string;
  trial_start: string;
  trial_end: string;
  days_remaining: number;
  days_used: number;
  used: boolean;
}

// ==================== API Service ====================

export const subscriptionPlanApi = {
  list: (active_only = true) =>
    apiClient.get<SubscriptionPlan[]>('/subscriptions/plans', { active_only }),

  getById: (id: string) =>
    apiClient.get<SubscriptionPlan>(`/subscriptions/plans/${id}`),
};

export const subscriptionApi = {
  list: (page = 1, limit = 20, status?: string) =>
    apiClient.get<Subscription[]>('/subscriptions', { page, limit, status_filter: status || undefined }),

  getById: (id: string) =>
    apiClient.get<Subscription>(`/subscriptions/${id}`),

  create: (data: {
    plan_id: string;
    patient_id?: string;
    payment_card_id?: string;
    trial_period_days?: number;
    proration_behavior?: string;
  }) =>
    apiClient.post<Subscription>('/subscriptions', data),

  cancel: (id: string, data: { cancel_at_period_end?: boolean; reason?: string; feedback?: string }) =>
    apiClient.post<Subscription>(`/subscriptions/${id}/cancel`, data),

  pause: (id: string, data: { paused_until?: string; reason?: string }) =>
    apiClient.post<Subscription>(`/subscriptions/${id}/pause`, data),

  resume: (id: string) =>
    apiClient.post<Subscription>(`/subscriptions/${id}/resume`),

  changePlan: (id: string, data: { new_plan_id: string; proration_behavior?: string }) =>
    apiClient.post<Subscription>(`/subscriptions/${id}/change-plan`, data),

  previewProration: (id: string, newPlanId: string) =>
    apiClient.get<ProrationPreview>(`/subscriptions/${id}/proration-preview`, { new_plan_id: newPlanId }),

  getTrial: (id: string) =>
    apiClient.get<TrialResponse>(`/subscriptions/${id}/trial`),

  // Usage
  recordUsage: (id: string, data: { quantity: string; description?: string; metadata?: Record<string, any> }) =>
    apiClient.post<UsageRecord>(`/subscriptions/${id}/usage`, data),

  getUsage: (id: string) =>
    apiClient.get<{ subscription_id: string; period_start: string; period_end: string; records: UsageRecord[]; summaries: UsageSummary[] }>(`/subscriptions/${id}/usage`),

  submitUsageBatch: (data: { subscription_id: string; items: Array<{ quantity: string; description?: string }> }) =>
    apiClient.post<{ records_created: number }>('/subscriptions/usage-billing/submit', data),

  // Dunning
  getDunningEvents: (id: string) =>
    apiClient.get<DunningEvent[]>(`/subscriptions/${id}/dunning`),

  // Stats
  getStats: () =>
    apiClient.get<SubscriptionStats>('/subscriptions/stats'),

  // Invoice History
  getInvoiceHistory: (id: string, limit = 50) =>
    apiClient.get<{ subscription_id: string; invoices: Array<{ id: string; number: string; amount_due: number; amount_paid: number; status: string; created: number; hosted_invoice_url?: string }> }>(
      `/subscriptions/${id}/invoice-history`, { limit }
    ),
};