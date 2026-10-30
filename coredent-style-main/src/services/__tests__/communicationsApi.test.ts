import { describe, it, expect, beforeEach } from 'vitest';
import { communicationsApi } from '../communicationsApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type {
  MessageTemplate,
  ReminderSchedule,
  Conversation,
  ConversationMessage,
} from '../communicationsApi';

const mockTemplate: MessageTemplate = {
  id: 'tpl-1',
  name: 'Recall Reminder',
  messageType: 'sms',
  subject: 'Time to come back',
  content: 'Hi {{firstName}}',
  category: 'recall',
  variables: ['firstName'],
  isActive: true,
  isDefault: false,
};

const mockReminder: ReminderSchedule = {
  id: 'rem-1',
  name: '24h before',
  reminderType: 'appointment',
  daysBefore: 0,
  hoursBefore: 24,
  minutesBefore: 0,
  messageType: 'sms',
  isActive: true,
  sendOnWeekends: false,
  maxReminders: 1,
  templateId: 'tpl-1',
};

const mockConversation: Conversation = {
  id: 'conv-1',
  patientId: 'patient-1',
  lastMessagePreview: 'See you tomorrow',
  lastMessageAt: '2026-06-21T12:00:00Z',
  unreadCount: 2,
  channel: 'sms',
};

const mockMessage: ConversationMessage = {
  id: 'msg-1',
  conversationId: 'conv-1',
  senderType: 'patient',
  content: 'Hello!',
  createdAt: '2026-06-21T12:00:00Z',
};

describe('communicationsApi', () => {
  beforeEach(() => server.resetHandlers());

  describe('templates', () => {
    it('listTemplates returns templates', async () => {
      server.use(
        http.get('/api/v1/communications/templates', () =>
          HttpResponse.json([mockTemplate]),
        ),
      );
      const result = await communicationsApi.listTemplates();
      expect(result.success).toBe(true);
      expect(result.data).toEqual([mockTemplate]);
    });

    it('getTemplate returns a single template', async () => {
      server.use(
        http.get('/api/v1/communications/templates/tpl-1', () =>
          HttpResponse.json(mockTemplate),
        ),
      );
      const result = await communicationsApi.getTemplate('tpl-1');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockTemplate);
    });

    it('createTemplate posts a new template', async () => {
      server.use(
        http.post('/api/v1/communications/templates', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockTemplate, ...body, id: 'tpl-2' }, { status: 201 });
        }),
      );
      const result = await communicationsApi.createTemplate({
        name: 'New',
        messageType: 'email',
        content: 'Body',
        category: 'marketing',
        variables: [],
        isActive: true,
        isDefault: false,
      });
      expect(result.success).toBe(true);
      expect(result.data?.id).toBe('tpl-2');
    });

    it('updateTemplate sends a PUT', async () => {
      server.use(
        http.put('/api/v1/communications/templates/tpl-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockTemplate, ...body });
        }),
      );
      const result = await communicationsApi.updateTemplate('tpl-1', { isActive: false });
      expect(result.success).toBe(true);
      expect(result.data?.isActive).toBe(false);
    });

    it('deleteTemplate removes a template', async () => {
      server.use(
        http.delete('/api/v1/communications/templates/tpl-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      const result = await communicationsApi.deleteTemplate('tpl-1');
      expect(result.success).toBe(true);
    });
  });

  describe('reminders', () => {
    it('listReminders returns reminder schedules', async () => {
      server.use(
        http.get('/api/v1/communications/reminders', () =>
          HttpResponse.json([mockReminder]),
        ),
      );
      const result = await communicationsApi.listReminders();
      expect(result.success).toBe(true);
      expect(result.data).toEqual([mockReminder]);
    });

    it('createReminder posts a new schedule', async () => {
      server.use(
        http.post('/api/v1/communications/reminders', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockReminder, ...body, id: 'rem-2' }, { status: 201 });
        }),
      );
      const result = await communicationsApi.createReminder({
        name: '48h before',
        reminderType: 'appointment',
        daysBefore: 0,
        hoursBefore: 48,
        minutesBefore: 0,
        messageType: 'email',
        isActive: true,
        sendOnWeekends: true,
        maxReminders: 2,
        templateId: 'tpl-1',
      });
      expect(result.success).toBe(true);
      expect(result.data?.id).toBe('rem-2');
    });

    it('updateReminder sends a PUT', async () => {
      server.use(
        http.put('/api/v1/communications/reminders/rem-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockReminder, ...body });
        }),
      );
      const result = await communicationsApi.updateReminder('rem-1', { isActive: false });
      expect(result.success).toBe(true);
      expect(result.data?.isActive).toBe(false);
    });

    it('deleteReminder removes a schedule', async () => {
      server.use(
        http.delete('/api/v1/communications/reminders/rem-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      const result = await communicationsApi.deleteReminder('rem-1');
      expect(result.success).toBe(true);
    });
  });

  describe('conversations', () => {
    it('listConversations returns conversations', async () => {
      server.use(
        http.get('/api/v1/communications/conversations', () =>
          HttpResponse.json([mockConversation]),
        ),
      );
      const result = await communicationsApi.listConversations();
      expect(result.success).toBe(true);
      expect(result.data).toEqual([mockConversation]);
    });

    it('getConversationMessages returns messages for a conversation', async () => {
      server.use(
        http.get('/api/v1/communications/conversations/conv-1/messages', () =>
          HttpResponse.json([mockMessage]),
        ),
      );
      const result = await communicationsApi.getConversationMessages('conv-1');
      expect(result.success).toBe(true);
      expect(result.data).toEqual([mockMessage]);
    });

    it('sendConversationMessage posts a reply', async () => {
      server.use(
        http.post('/api/v1/communications/conversations/conv-1/messages', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockMessage, ...body, id: 'msg-2' }, { status: 201 });
        }),
      );
      const result = await communicationsApi.sendConversationMessage('conv-1', {
        conversationId: 'conv-1',
        senderType: 'staff',
        content: 'Hello, how can we help?',
      });
      expect(result.success).toBe(true);
      expect(result.data?.id).toBe('msg-2');
    });
  });

  describe('summary', () => {
    it('getSummary returns the communications summary', async () => {
      server.use(
        http.get('/api/v1/communications/settings', () =>
          HttpResponse.json({
            unreadMessages: 5,
            messages: { totalSent: 120, deliveryRate: 98.5 },
            reminders: { pending: 4 },
          }),
        ),
      );
      const result = await communicationsApi.getSummary();
      expect(result.success).toBe(true);
      expect(result.data?.unreadMessages).toBe(5);
      expect(result.data?.messages.deliveryRate).toBe(98.5);
    });
  });
});
