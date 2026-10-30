import { describe, it, expect, beforeEach } from 'vitest';
import { subscriptionApi, subscriptionPlanApi } from '../subscriptionsApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

const mockPlan = {
  id: 'plan-1',
  name: 'Pro',
  description: 'Pro plan',
  short_description: 'Pro',
  amount: '99.00',
  currency: 'USD',
  interval: 'monthly' as const,
  trial_period_days: 14,
  features: ['Appointments', 'Reports'],
  limits: null,
  is_active: true,
  is_recommended: true,
  is_usage_based: false,
  usage_meter_name: null,
  usage_unit_label: null,
  included_usage: '0',
  overage_rate: '0',
  stripe_price_id: 'price_1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockSubscription = {
  id: 'sub-1',
  practice_id: 'prac-1',
  patient_id: null,
  plan_id: 'plan-1',
  status: 'active' as const,
  interval: 'monthly',
  current_period_start: '2026-06-01T00:00:00Z',
  current_period_end: '2026-07-01T00:00:00Z',
  next_billing_date: '2026-07-01T00:00:00Z',
  trial_start: null,
  trial_end: null,
  trial_used: false,
  cancel_at_period_end: false,
  canceled_at: null,
  cancellation_reason: null,
  paused_at: null,
  paused_until: null,
  current_usage: '0',
  current_overage: '0',
  dunning_retry_count: 0,
  last_payment_error: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('subscriptionPlanApi', () => {
  beforeEach(() => server.resetHandlers());

  it('list returns plans', async () => {
    server.use(
      http.get('/api/v1/subscriptions/plans', () => HttpResponse.json([mockPlan])),
    );
    const result = await subscriptionPlanApi.list();
    expect(result.data).toEqual([mockPlan]);
  });

  it('getById returns a single plan', async () => {
    server.use(
      http.get('/api/v1/subscriptions/plans/plan-1', () => HttpResponse.json(mockPlan)),
    );
    const result = await subscriptionPlanApi.getById('plan-1');
    expect(result.data?.id).toBe('plan-1');
  });
});

describe('subscriptionApi', () => {
  beforeEach(() => server.resetHandlers());

  it('list returns subscriptions', async () => {
    server.use(
      http.get('/api/v1/subscriptions', () => HttpResponse.json([mockSubscription])),
    );
    const result = await subscriptionApi.list();
    expect(result.data).toEqual([mockSubscription]);
  });

  it('getById returns a single subscription', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1', () => HttpResponse.json(mockSubscription)),
    );
    const result = await subscriptionApi.getById('sub-1');
    expect(result.data?.id).toBe('sub-1');
  });

  it('create posts a new subscription', async () => {
    server.use(
      http.post('/api/v1/subscriptions', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockSubscription, ...body, id: 'sub-2' }, { status: 201 });
      }),
    );
    const result = await subscriptionApi.create({ plan_id: 'plan-1' });
    expect(result.data?.id).toBe('sub-2');
  });

  it('cancel posts a cancellation', async () => {
    server.use(
      http.post('/api/v1/subscriptions/sub-1/cancel', () =>
        HttpResponse.json({ ...mockSubscription, cancel_at_period_end: true }),
      ),
    );
    const result = await subscriptionApi.cancel('sub-1', { cancel_at_period_end: true });
    expect(result.data?.cancel_at_period_end).toBe(true);
  });

  it('pause posts a pause', async () => {
    server.use(
      http.post('/api/v1/subscriptions/sub-1/pause', () =>
        HttpResponse.json({ ...mockSubscription, status: 'paused' }),
      ),
    );
    const result = await subscriptionApi.pause('sub-1', { paused_until: '2026-09-01' });
    expect(result.data?.status).toBe('paused');
  });

  it('resume posts a resume', async () => {
    server.use(
      http.post('/api/v1/subscriptions/sub-1/resume', () =>
        HttpResponse.json({ ...mockSubscription, status: 'active' }),
      ),
    );
    const result = await subscriptionApi.resume('sub-1');
    expect(result.data?.status).toBe('active');
  });

  it('changePlan posts a plan change', async () => {
    server.use(
      http.post('/api/v1/subscriptions/sub-1/change-plan', () =>
        HttpResponse.json({ ...mockSubscription, plan_id: 'plan-2' }),
      ),
    );
    const result = await subscriptionApi.changePlan('sub-1', { new_plan_id: 'plan-2' });
    expect(result.data?.plan_id).toBe('plan-2');
  });

  it('previewProration returns a proration preview', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1/proration-preview', () =>
        HttpResponse.json({
          old_plan: { name: 'Basic', amount: 49 },
          new_plan: { name: 'Pro', amount: 99 },
          days_remaining: 15,
          total_days: 30,
          proration_amount: 50,
          proration_credit: true,
          effective_immediately: true,
        }),
      ),
    );
    const result = await subscriptionApi.previewProration('sub-1', 'plan-2');
    expect(result.data?.proration_credit).toBe(true);
  });

  it('getTrial returns trial details', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1/trial', () =>
        HttpResponse.json({
          subscription_id: 'sub-1',
          plan_name: 'Pro',
          trial_start: '2026-06-01',
          trial_end: '2026-06-15',
          days_remaining: 10,
          days_used: 4,
          used: true,
        }),
      ),
    );
    const result = await subscriptionApi.getTrial('sub-1');
    expect(result.data?.days_remaining).toBe(10);
  });

  it('recordUsage posts a usage record', async () => {
    server.use(
      http.post('/api/v1/subscriptions/sub-1/usage', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: 'u-1', subscription_id: 'sub-1', timestamp: '2026-06-22T00:00:00Z', ...body },
          { status: 201 },
        );
      }),
    );
    const result = await subscriptionApi.recordUsage('sub-1', { quantity: '5' });
    expect(result.data?.id).toBe('u-1');
  });

  it('getUsage returns usage records', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1/usage', () =>
        HttpResponse.json({
          subscription_id: 'sub-1',
          period_start: '2026-06-01',
          period_end: '2026-07-01',
          records: [],
          summaries: [],
        }),
      ),
    );
    const result = await subscriptionApi.getUsage('sub-1');
    expect(result.data?.subscription_id).toBe('sub-1');
  });

  it('submitUsageBatch posts a batch', async () => {
    server.use(
      http.post('/api/v1/subscriptions/usage-billing/submit', () =>
        HttpResponse.json({ records_created: 5 }),
      ),
    );
    const result = await subscriptionApi.submitUsageBatch({
      subscription_id: 'sub-1',
      items: [{ quantity: '1' }],
    });
    expect(result.data?.records_created).toBe(5);
  });

  it('getDunningEvents returns events', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1/dunning', () => HttpResponse.json([])),
    );
    const result = await subscriptionApi.getDunningEvents('sub-1');
    expect(result.data).toEqual([]);
  });

  it('getStats returns subscription stats', async () => {
    server.use(
      http.get('/api/v1/subscriptions/stats', () =>
        HttpResponse.json({
          total_active: 100,
          total_trials: 5,
          total_past_due: 2,
          total_canceled_this_month: 1,
          mrr: '9900',
          mrr_growth_percent: 5.5,
          churn_rate: 1.2,
          trial_conversion_rate: 30,
          average_lifetime_days: 180,
        }),
      ),
    );
    const result = await subscriptionApi.getStats();
    expect(result.data?.total_active).toBe(100);
  });

  it('getInvoiceHistory returns invoice history', async () => {
    server.use(
      http.get('/api/v1/subscriptions/sub-1/invoice-history', () =>
        HttpResponse.json({
          subscription_id: 'sub-1',
          invoices: [
            {
              id: 'inv-1',
              number: 'INV-001',
              amount_due: 99,
              amount_paid: 99,
              status: 'paid',
              created: 1700000000,
            },
          ],
        }),
      ),
    );
    const result = await subscriptionApi.getInvoiceHistory('sub-1');
    expect(result.data?.invoices).toHaveLength(1);
  });
});
