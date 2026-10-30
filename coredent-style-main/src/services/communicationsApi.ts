// ============================================
// CoreDent PMS - Communications API Service
// API calls and contracts for patient messaging, reminders, and conversations
// ============================================

import { apiClient } from '@/services/api';
import type { ApiResponse } from '@/types/api';

// --------------------------------------------
// Domain types (mirrors app/schemas/communication.py)
// --------------------------------------------

export type MessageType = 'sms' | 'email';

export type ReminderType = 'appointment' | 'recall' | 'treatment';

export type MessageCategory =
  | 'appointment'
  | 'recall'
  | 'treatment'
  | 'billing'
  | 'marketing';

export interface MessageTemplate {
  id: string;
  name: string;
  messageType: MessageType;
  subject?: string;
  content: string;
  category: string;
  variables: string[];
  isActive: boolean;
  isDefault: boolean;
}

/** Payload used when creating a template (server assigns the id). */
export type MessageTemplateCreate = Omit<MessageTemplate, 'id'>;

/** Payload used when updating a template. */
export type MessageTemplateUpdate = Partial<MessageTemplateCreate>;

export interface ReminderSchedule {
  id: string;
  name: string;
  reminderType: ReminderType;
  daysBefore: number;
  hoursBefore: number;
  minutesBefore: number;
  messageType: MessageType;
  isActive: boolean;
  sendOnWeekends: boolean;
  maxReminders: number;
  templateId: string;
}

/** Payload used when creating a reminder schedule. */
export type ReminderScheduleCreate = Omit<ReminderSchedule, 'id'>;

/** Payload used when updating a reminder schedule. */
export type ReminderScheduleUpdate = Partial<ReminderScheduleCreate>;

export type ConversationChannel = 'sms' | 'email';

export interface Conversation {
  id: string;
  patientId: string;
  lastMessagePreview?: string;
  lastMessageAt?: string;
  unreadCount: number;
  channel: ConversationChannel;
}

export type ConversationSenderType = 'patient' | 'staff' | 'system';

export interface ConversationMessage {
  id: string;
  conversationId: string;
  senderType: ConversationSenderType;
  content: string;
  createdAt: string;
}

/** Payload used when posting a message into a conversation. */
export interface ConversationMessageCreate {
  conversationId: string;
  senderType: ConversationSenderType;
  content: string;
}

export interface CommunicationSummary {
  unreadMessages: number;
  messages: {
    totalSent: number;
    deliveryRate: number;
  };
  reminders: {
    pending: number;
  };
}

// --------------------------------------------
// API surface
// --------------------------------------------

export const communicationsApi = {
  // Templates
  listTemplates: () =>
    apiClient.get<MessageTemplate[]>('/communications/templates'),

  getTemplate: (id: string) =>
    apiClient.get<MessageTemplate>(`/communications/templates/${id}`),

  createTemplate: (data: MessageTemplateCreate) =>
    apiClient.post<MessageTemplate>('/communications/templates', data),

  updateTemplate: (id: string, data: MessageTemplateUpdate) =>
    apiClient.put<MessageTemplate>(`/communications/templates/${id}`, data),

  deleteTemplate: (id: string) =>
    apiClient.delete<void>(`/communications/templates/${id}`),

  // Reminders
  listReminders: () =>
    apiClient.get<ReminderSchedule[]>('/communications/reminders'),

  createReminder: (data: ReminderScheduleCreate) =>
    apiClient.post<ReminderSchedule>('/communications/reminders', data),

  updateReminder: (id: string, data: ReminderScheduleUpdate) =>
    apiClient.put<ReminderSchedule>(`/communications/reminders/${id}`, data),

  deleteReminder: (id: string) =>
    apiClient.delete<void>(`/communications/reminders/${id}`),

  // Conversations
  listConversations: () =>
    apiClient.get<Conversation[]>('/communications/conversations'),

  getConversationMessages: (conversationId: string): Promise<ApiResponse<ConversationMessage[]>> =>
    apiClient.get<ConversationMessage[]>(
      `/communications/conversations/${conversationId}/messages`,
    ),

  sendConversationMessage: (
    conversationId: string,
    data: ConversationMessageCreate,
  ): Promise<ApiResponse<ConversationMessage>> =>
    apiClient.post<ConversationMessage>(
      `/communications/conversations/${conversationId}/messages`,
      data,
    ),

  // Summary
  getSummary: () =>
    apiClient.get<CommunicationSummary>('/communications/settings'),
};
