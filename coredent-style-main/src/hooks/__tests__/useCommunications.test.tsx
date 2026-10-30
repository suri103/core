import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { communicationsApi } from "@/services/communicationsApi";
import { useCommunications } from "../useCommunications";

vi.mock("@/services/communicationsApi", () => ({
  communicationsApi: {
    createReminder: vi.fn(),
    createTemplate: vi.fn(),
    deleteReminder: vi.fn(),
    deleteTemplate: vi.fn(),
    getConversationMessages: vi.fn(),
    getSummary: vi.fn(),
    listConversations: vi.fn(),
    listReminders: vi.fn(),
    listTemplates: vi.fn(),
    sendConversationMessage: vi.fn(),
    updateReminder: vi.fn(),
    updateTemplate: vi.fn(),
  },
}));

const template = {
  id: "template-1",
  name: "Recall",
  messageType: "sms" as const,
  content: "Please schedule your recall",
  category: "recall",
  variables: [],
  isActive: true,
  isDefault: false,
};

describe("useCommunications", () => {
  beforeEach(() => vi.clearAllMocks());

  it("preserves previously loaded templates and surfaces a later outage", async () => {
    vi.mocked(communicationsApi.listTemplates)
      .mockResolvedValueOnce({ success: true, data: [template] })
      .mockResolvedValueOnce({
        success: false,
        error: { code: "UNAVAILABLE", message: "Messaging unavailable" },
      });

    const { result } = renderHook(() => useCommunications());
    await act(async () => result.current.fetchTemplates());
    expect(result.current.templates).toEqual([template]);

    await act(async () => {
      await expect(result.current.fetchTemplates()).rejects.toThrow("Messaging unavailable");
    });

    expect(result.current.templates).toEqual([template]);
    expect(result.current.error?.message).toBe("Messaging unavailable");
  });

  it("does not mutate local templates when an update is rejected", async () => {
    vi.mocked(communicationsApi.listTemplates).mockResolvedValue({ success: true, data: [template] });
    vi.mocked(communicationsApi.updateTemplate).mockResolvedValue({
      success: false,
      error: { code: "CONFLICT", message: "Template is locked" },
    });

    const { result } = renderHook(() => useCommunications());
    await act(async () => result.current.fetchTemplates());

    await act(async () => {
      await expect(
        result.current.updateTemplate(template.id, { name: "Changed" }),
      ).rejects.toThrow("Template is locked");
    });

    expect(result.current.templates).toEqual([template]);
  });

  it("creates a template successfully", async () => {
    vi.mocked(communicationsApi.createTemplate).mockResolvedValue({ success: true, data: template });
    const { result } = renderHook(() => useCommunications());
    await act(async () => {
      const created = await result.current.createTemplate({ name: "Recall", messageType: "sms", content: "Please schedule", category: "recall" } as any);
      expect(created).toEqual(template);
    });
    expect(result.current.templates).toContainEqual(template);
  });

  it("updates a template successfully", async () => {
    vi.mocked(communicationsApi.listTemplates).mockResolvedValue({ success: true, data: [template] });
    const updated = { ...template, name: "Updated Recall" };
    vi.mocked(communicationsApi.updateTemplate).mockResolvedValue({ success: true, data: updated });

    const { result } = renderHook(() => useCommunications());
    await act(async () => result.current.fetchTemplates());
    await act(async () => {
      const resultUpdated = await result.current.updateTemplate(template.id, { name: "Updated Recall" });
      expect(resultUpdated).toEqual(updated);
    });
    expect(result.current.templates).toContainEqual(updated);
  });

  it("deletes a template successfully", async () => {
    vi.mocked(communicationsApi.listTemplates).mockResolvedValue({ success: true, data: [template] });
    vi.mocked(communicationsApi.deleteTemplate).mockResolvedValue({ success: true, data: undefined });

    const { result } = renderHook(() => useCommunications());
    await act(async () => result.current.fetchTemplates());
    await act(async () => {
      await result.current.deleteTemplate(template.id);
    });
    expect(result.current.templates).toHaveLength(0);
  });

  it("handles non-Error cause in runRead catch block", async () => {
    vi.mocked(communicationsApi.listTemplates).mockImplementation(() => {
      throw "string exception";
    });

    const { result } = renderHook(() => useCommunications());
    await act(async () => {
      await expect(result.current.fetchTemplates()).rejects.toThrow("Communication service unavailable");
    });
    expect(result.current.error).toEqual(new Error("Communication service unavailable"));
  });

  it("fetches, creates, updates, and deletes reminders successfully", async () => {
    const reminder = { id: "rem-1", name: "Appt Reminder", triggerDays: 1, templateId: "template-1", isActive: true, reminderType: "appointment" as const, daysBefore: 1, hoursBefore: 0, minutesBefore: 0, messageType: "sms" as const, sendOnWeekends: true, maxReminders: 1 };
    const reminder2 = { ...reminder, id: "rem-2" };
    vi.mocked(communicationsApi.listReminders).mockResolvedValue({ success: true, data: [reminder] });
    vi.mocked(communicationsApi.createReminder).mockResolvedValue({ success: true, data: reminder2 });
    const updated = { ...reminder, name: "Updated Reminder" };
    vi.mocked(communicationsApi.updateReminder).mockResolvedValue({ success: true, data: updated });
    vi.mocked(communicationsApi.deleteReminder).mockResolvedValue({ success: true, data: undefined });

    const { result } = renderHook(() => useCommunications());
    
    // Fetch
    await act(async () => result.current.fetchReminders());
    expect(result.current.reminders).toEqual([reminder]);

    // Create
    await act(async () => {
      await result.current.createReminder(reminder2 as any);
    });
    expect(result.current.reminders).toHaveLength(2);

    // Update
    await act(async () => {
      await result.current.updateReminder(reminder.id, { name: "Updated Reminder" });
    });
    expect(result.current.reminders).toContainEqual(updated);

    // Delete
    await act(async () => {
      await result.current.deleteReminder(reminder.id);
    });
    expect(result.current.reminders).toHaveLength(1);
    expect(result.current.reminders[0].id).toBe("rem-2");
  });

  it("fetches conversations, selects conversation, and sends message successfully", async () => {
    const conversation = { id: "conv-1", patientId: "p-1", patientName: "Jamie", lastMessagePreview: "hello", lastMessageAt: "2026-06-22T00:00:00Z", unreadCount: 0, channel: "sms" as const };
    const message = { id: "msg-1", conversationId: "conv-1", content: "hello", createdAt: "2026-06-22T00:00:00Z", sender: "clinic" as const, senderType: "staff" as const, status: "sent" as const };

    vi.mocked(communicationsApi.listConversations).mockResolvedValue({ success: true, data: [conversation] });
    vi.mocked(communicationsApi.getConversationMessages).mockResolvedValue({ success: true, data: [message] });
    vi.mocked(communicationsApi.sendConversationMessage).mockResolvedValue({ success: true, data: message });

    const { result } = renderHook(() => useCommunications());

    // Fetch conversations
    await act(async () => result.current.fetchConversations());
    expect(result.current.conversations).toEqual([conversation]);

    // Select conversation
    await act(async () => result.current.selectConversation(conversation.id));
    expect(result.current.conversationMessages).toEqual([message]);

    // Send message
    await act(async () => {
      await result.current.sendConversationMessage(conversation.id, { content: "hello", senderType: "staff" as const });
    });
    expect(result.current.conversationMessages).toContainEqual(message);
  });

  it("loads the communication summary through the typed service", async () => {
    const summary = {
      unreadMessages: 2,
      messages: { totalSent: 10, deliveryRate: 98 },
      reminders: { pending: 3 },
    };
    vi.mocked(communicationsApi.getSummary).mockResolvedValue({ success: true, data: summary });

    const { result } = renderHook(() => useCommunications());
    await act(async () => result.current.fetchSummary());

    await waitFor(() => expect(result.current.summary).toEqual(summary));
    expect(communicationsApi.getSummary).toHaveBeenCalledOnce();
  });
});