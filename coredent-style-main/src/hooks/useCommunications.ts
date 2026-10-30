import { useCallback, useState } from "react";
import { requireApiData, requireApiSuccess } from "@/services/apiResponse";
import {
  communicationsApi,
  type CommunicationSummary,
  type Conversation,
  type ConversationMessage,
  type ConversationMessageCreate,
  type MessageTemplate,
  type MessageTemplateCreate,
  type MessageTemplateUpdate,
  type ReminderSchedule,
  type ReminderScheduleCreate,
  type ReminderScheduleUpdate,
} from "@/services/communicationsApi";

export function useCommunications() {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [reminders, setReminders] = useState<ReminderSchedule[]>([]);
  const [remindersLoading, setRemindersLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [conversationMessages, setConversationMessages] = useState<ConversationMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [summary, setSummary] = useState<CommunicationSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const runRead = useCallback(async <T,>(
    load: () => Promise<T>,
    setLoading: (loading: boolean) => void,
  ): Promise<T> => {
    setLoading(true);
    try {
      const data = await load();
      setError(null);
      return data;
    } catch (cause) {
      const nextError = cause instanceof Error
        ? cause
        : new Error("Communication service unavailable");
      setError(nextError);
      throw nextError;
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    const data = await runRead(
      async () => requireApiData(
        await communicationsApi.listTemplates(),
        "Failed to load message templates",
      ),
      setTemplatesLoading,
    );
    setTemplates(data);
  }, [runRead]);

  const createTemplate = async (template: MessageTemplateCreate) => {
    const created = requireApiData(
      await communicationsApi.createTemplate(template),
      "Failed to create message template",
    );
    setTemplates((current) => [...current, created]);
    return created;
  };

  const updateTemplate = async (id: string, template: MessageTemplateUpdate) => {
    const updated = requireApiData(
      await communicationsApi.updateTemplate(id, template),
      "Failed to update message template",
    );
    setTemplates((current) => current.map((item) => item.id === id ? updated : item));
    return updated;
  };

  const deleteTemplate = async (id: string) => {
    requireApiSuccess(
      await communicationsApi.deleteTemplate(id),
      "Failed to delete message template",
    );
    setTemplates((current) => current.filter((item) => item.id !== id));
  };

  const fetchReminders = useCallback(async () => {
    const data = await runRead(
      async () => requireApiData(
        await communicationsApi.listReminders(),
        "Failed to load reminder schedules",
      ),
      setRemindersLoading,
    );
    setReminders(data);
  }, [runRead]);

  const createReminder = async (reminder: ReminderScheduleCreate) => {
    const created = requireApiData(
      await communicationsApi.createReminder(reminder),
      "Failed to create reminder schedule",
    );
    setReminders((current) => [...current, created]);
    return created;
  };

  const updateReminder = async (id: string, reminder: ReminderScheduleUpdate) => {
    const updated = requireApiData(
      await communicationsApi.updateReminder(id, reminder),
      "Failed to update reminder schedule",
    );
    setReminders((current) => current.map((item) => item.id === id ? updated : item));
    return updated;
  };

  const deleteReminder = async (id: string) => {
    requireApiSuccess(
      await communicationsApi.deleteReminder(id),
      "Failed to delete reminder schedule",
    );
    setReminders((current) => current.filter((item) => item.id !== id));
  };

  const fetchConversations = useCallback(async () => {
    const data = await runRead(
      async () => requireApiData(
        await communicationsApi.listConversations(),
        "Failed to load conversations",
      ),
      setConversationsLoading,
    );
    setConversations(data);
  }, [runRead]);

  const selectConversation = async (conversationId: string) => {
    const data = await runRead(
      async () => requireApiData(
        await communicationsApi.getConversationMessages(conversationId),
        "Failed to load conversation messages",
      ),
      setMessagesLoading,
    );
    setConversationMessages(data);
  };

  const sendConversationMessage = async (
    conversationId: string,
    message: Omit<ConversationMessageCreate, "conversationId">,
  ) => {
    const created = requireApiData(
      await communicationsApi.sendConversationMessage(conversationId, {
        ...message,
        conversationId,
      }),
      "Failed to send message",
    );
    setConversationMessages((current) => [...current, created]);
    setConversations((current) => current.map((conversation) =>
      conversation.id === conversationId
        ? {
            ...conversation,
            lastMessagePreview: created.content,
            lastMessageAt: created.createdAt,
          }
        : conversation,
    ));
    return created;
  };

  const fetchSummary = useCallback(async () => {
    const data = await runRead(
      async () => requireApiData(
        await communicationsApi.getSummary(),
        "Failed to load communication summary",
      ),
      setSummaryLoading,
    );
    setSummary(data);
  }, [runRead]);

  return {
    templates,
    templatesLoading,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    reminders,
    remindersLoading,
    fetchReminders,
    createReminder,
    updateReminder,
    deleteReminder,
    conversations,
    conversationsLoading,
    fetchConversations,
    selectConversation,
    conversationMessages,
    messagesLoading,
    sendConversationMessage,
    summary,
    summaryLoading,
    fetchSummary,
    error,
  };
}