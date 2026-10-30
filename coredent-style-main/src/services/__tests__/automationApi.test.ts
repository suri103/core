import { describe, it, expect, beforeEach } from 'vitest';
import { automationApi, triggerAutomation } from '../automationApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { AutomationWebhook } from '@/types/automation';

const mockWebhook: AutomationWebhook = {
  id: 'hook-1',
  name: 'Slack notifier',
  url: 'https://hooks.slack.com/services/AAA/BBB',
  event: 'appointment_booked',
  isActive: true,
  createdAt: '2026-06-01T00:00:00Z',
  updatedAt: '2026-06-01T00:00:00Z',
};

describe('automationApi', () => {
  beforeEach(() => server.resetHandlers());

  it('getWebhooks returns the list', async () => {
    server.use(
      http.get('/api/v1/automations/webhooks', () =>
        HttpResponse.json([mockWebhook]),
      ),
    );
    const result = await automationApi.getWebhooks();
    expect(result).toEqual([mockWebhook]);
  });

  it('getWebhooksByEvent passes the event as a query param', async () => {
    server.use(
      http.get('/api/v1/automations/webhooks', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('event')).toBe('appointment_booked');
        return HttpResponse.json([mockWebhook]);
      }),
    );
    const result = await automationApi.getWebhooksByEvent('appointment_booked');
    expect(result).toEqual([mockWebhook]);
  });

  it('createWebhook posts a new webhook', async () => {
    server.use(
      http.post('/api/v1/automations/webhooks', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockWebhook, ...body, id: 'hook-2' }, { status: 201 });
      }),
    );
    const result = await automationApi.createWebhook({
      name: 'New',
      url: 'https://example.com/hook',
      event: 'appointment_booked',
      isActive: true,
    });
    expect(result.id).toBe('hook-2');
  });

  it('updateWebhook sends a PUT', async () => {
    server.use(
      http.put('/api/v1/automations/webhooks/hook-1', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockWebhook, ...body });
      }),
    );
    const result = await automationApi.updateWebhook('hook-1', { isActive: false });
    expect(result.isActive).toBe(false);
  });

  it('deleteWebhook resolves', async () => {
    server.use(
      http.delete('/api/v1/automations/webhooks/hook-1', () =>
        HttpResponse.json({ message: 'Deleted' }),
      ),
    );
    await expect(automationApi.deleteWebhook('hook-1')).resolves.toBeUndefined();
  });

  it('toggleWebhook posts the toggle', async () => {
    server.use(
      http.post('/api/v1/automations/webhooks/hook-1/toggle', () =>
        HttpResponse.json({ ...mockWebhook, isActive: false }),
      ),
    );
    const result = await automationApi.toggleWebhook('hook-1');
    expect(result.isActive).toBe(false);
  });

  it('triggerWebhook posts an event and returns trigger count', async () => {
    server.use(
      http.post('/api/v1/automations/trigger', () =>
        HttpResponse.json({ success: true, triggeredCount: 2 }),
      ),
    );
    const result = await automationApi.triggerWebhook('appointment_booked', {
      patientId: 'p-1',
    } as never);
    expect(result.triggeredCount).toBe(2);
  });

  it('testWebhook returns whether the webhook is reachable', async () => {
    server.use(
      http.post('/api/v1/automations/test', () =>
        HttpResponse.json({ success: true }),
      ),
    );
    const result = await automationApi.testWebhook('https://example.com/hook', 'tok');
    expect(result).toBe(true);
  });

  it('triggerAutomation is a thin wrapper over triggerWebhook', async () => {
    server.use(
      http.post('/api/v1/automations/trigger', () =>
        HttpResponse.json({ success: true, triggeredCount: 1 }),
      ),
    );
    await expect(
      triggerAutomation('invoice_created', { invoiceId: 'i-1' } as never),
    ).resolves.toBeUndefined();
  });
});
