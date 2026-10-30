import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Communications from "../Communications";

const {
  createReminder,
  createTemplate,
  deleteReminder,
  deleteTemplate,
  fetchConversations,
  fetchReminders,
  fetchSummary,
  fetchTemplates,
  mockCommunications,
  selectConversation,
  sendConversationMessage,
  updateReminder,
  updateTemplate,
} = vi.hoisted(() => ({
  createReminder: vi.fn(),
  createTemplate: vi.fn(),
  deleteReminder: vi.fn(),
  deleteTemplate: vi.fn(),
  fetchConversations: vi.fn(),
  fetchReminders: vi.fn(),
  fetchSummary: vi.fn(),
  fetchTemplates: vi.fn(),
  mockCommunications: vi.fn(),
  selectConversation: vi.fn(),
  sendConversationMessage: vi.fn(),
  updateReminder: vi.fn(),
  updateTemplate: vi.fn(),
}));

vi.mock("@/hooks/useCommunications", () => ({
  useCommunications: () => mockCommunications(),
}));

const templates = [
  {
    id: "template-1",
    name: "Recall Template",
    messageType: "email",
    subject: "Time for your recall",
    content: "Hi [patient_name], please book your recall.",
    category: "recall",
    variables: ["patient_name", "practice_name"],
    isActive: true,
    isDefault: true,
  },
  {
    id: "template-2",
    name: "Treatment Follow-up",
    messageType: "sms",
    subject: "",
    content: "How are you feeling after treatment?",
    category: "treatment",
    variables: [],
    isActive: false,
    isDefault: false,
  },
];

const reminders = [
  {
    id: "reminder-1",
    name: "Recall Reminder",
    reminderType: "recall",
    daysBefore: 1,
    hoursBefore: 2,
    minutesBefore: 15,
    messageType: "email",
    isActive: true,
    sendOnWeekends: false,
    maxReminders: 3,
    templateId: "template-1",
  },
  {
    id: "reminder-2",
    name: "Same-time Reminder",
    reminderType: "appointment",
    daysBefore: 0,
    hoursBefore: 0,
    minutesBefore: 0,
    messageType: "sms",
    isActive: false,
    sendOnWeekends: true,
    maxReminders: 1,
    templateId: "template-2",
  },
];

function baseCommunicationsState() {
  return {
    templates,
    templatesLoading: false,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    reminders,
    remindersLoading: false,
    fetchReminders,
    createReminder,
    updateReminder,
    deleteReminder,
    conversations: [
      {
        id: "conversation-1",
        patientId: "patient-alpha",
        channel: "email",
        lastMessagePreview: "",
        lastMessageAt: "",
        unreadCount: 0,
      },
    ],
    conversationsLoading: false,
    fetchConversations,
    selectConversation,
    conversationMessages: [
      {
        id: "message-1",
        conversationId: "conversation-1",
        senderType: "patient",
        content: "Can I move my appointment?",
        createdAt: "2026-06-20T10:00:00Z",
      },
    ],
    sendConversationMessage,
    summary: {
      unreadMessages: 0,
      messages: { totalSent: 8, deliveryRate: 99 },
      reminders: { pending: 2 },
    },
    summaryLoading: false,
    fetchSummary,
    error: null,
  };
}

describe("high-impact Communications workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchTemplates.mockResolvedValue(undefined);
    fetchReminders.mockResolvedValue(undefined);
    fetchConversations.mockResolvedValue(undefined);
    fetchSummary.mockResolvedValue(undefined);
    createTemplate.mockResolvedValue(templates[0]);
    updateTemplate.mockResolvedValue(templates[0]);
    deleteTemplate.mockResolvedValue(undefined);
    createReminder.mockResolvedValue(reminders[0]);
    updateReminder.mockResolvedValue(reminders[0]);
    deleteReminder.mockResolvedValue(undefined);
    selectConversation.mockResolvedValue(undefined);
    sendConversationMessage.mockResolvedValue({ id: "message-2" });
    mockCommunications.mockImplementation(baseCommunicationsState);
  });

  it("covers template create/edit/delete workflows", async () => {
    const user = userEvent.setup();
    render(<Communications />);

    await waitFor(() => expect(fetchTemplates).toHaveBeenCalled());
    await user.click(screen.getByRole("tab", { name: "Templates" }));

    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Variables: patient_name, practice_name")).toBeInTheDocument();

    const recallCard = screen.getByText("Recall Template").closest(".border");
    expect(recallCard).toBeTruthy();
    await user.click(within(recallCard as HTMLElement).getAllByRole("button")[0]);

    expect(screen.getByRole("dialog", { name: "Edit Template" })).toBeInTheDocument();
    await user.clear(screen.getByDisplayValue("Recall Template"));
    await user.type(screen.getByPlaceholderText("Appointment Reminder"), "Updated Recall");
    await user.clear(screen.getByDisplayValue("Time for your recall"));
    await user.type(screen.getByPlaceholderText("Email subject line"), "Updated subject");
    await user.clear(screen.getByDisplayValue("Hi [patient_name], please book your recall."));
    await user.type(screen.getByPlaceholderText(/Hi \[patient_name\]/i), "Updated content");
    await user.click(screen.getByRole("switch", { name: "Set as default for this type" }));
    await user.click(screen.getByRole("button", { name: "Save Template" }));

    await waitFor(() =>
      expect(updateTemplate).toHaveBeenCalledWith(
        "template-1",
        expect.objectContaining({
          name: "Updated Recall",
          subject: "Updated subject",
          content: "Updated content",
          isDefault: false,
        }),
      ),
    );

    const treatmentCard = screen.getByText("Treatment Follow-up").closest(".border");
    expect(treatmentCard).toBeTruthy();
    await user.click(within(treatmentCard as HTMLElement).getAllByRole("button")[1]);
    expect(deleteTemplate).toHaveBeenCalledWith("template-2");

    await user.click(screen.getByRole("button", { name: "Add Template" }));
    await user.type(screen.getByPlaceholderText("Appointment Reminder"), "New SMS Template");
    await user.type(screen.getByPlaceholderText(/Hi \[patient_name\]/i), "Fresh template body");
    await user.click(screen.getByRole("switch", { name: "Active" }));
    await user.click(screen.getByRole("button", { name: "Save Template" }));

    await waitFor(() =>
      expect(createTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "New SMS Template",
          content: "Fresh template body",
          isActive: false,
        }),
      ),
    );
  });

  it("covers reminder create/edit/delete workflows and communication settings toggles", async () => {
    const user = userEvent.setup();
    render(<Communications />);

    await user.click(screen.getByRole("tab", { name: "Reminders" }));

    expect(screen.getByText("1 day(s) before, 2 hour(s) before, 15 minute(s) before")).toBeInTheDocument();
    expect(screen.getByText("At scheduled time")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();

    const reminderRow = screen.getByText("Recall Reminder").closest("tr");
    expect(reminderRow).toBeTruthy();
    await user.click(within(reminderRow as HTMLElement).getAllByRole("button")[0]);
    expect(screen.getByRole("dialog", { name: "Edit Reminder" })).toBeInTheDocument();
    await user.click(screen.getByRole("switch", { name: "Send on weekends" }));
    await user.click(screen.getByRole("button", { name: "Save Reminder" }));

    await waitFor(() =>
      expect(updateReminder).toHaveBeenCalledWith(
        "reminder-1",
        expect.objectContaining({
          name: "Recall Reminder",
          sendOnWeekends: true,
          templateId: "template-1",
        }),
      ),
    );

    const sameTimeRow = screen.getByText("Same-time Reminder").closest("tr");
    expect(sameTimeRow).toBeTruthy();
    await user.click(within(sameTimeRow as HTMLElement).getAllByRole("button")[1]);
    expect(deleteReminder).toHaveBeenCalledWith("reminder-2");

    await user.click(screen.getByRole("button", { name: "Add Reminder" }));
    await user.type(screen.getByPlaceholderText("1 Day Before Appointment"), "New Reminder");
    const reminderDialog = screen.getByRole("dialog", { name: "Create Reminder Schedule" });
    await user.click(within(reminderDialog).getAllByRole("combobox")[2]);
    await user.click(await screen.findByRole("option", { name: "Recall Template" }));
    await user.click(screen.getByRole("button", { name: "Save Reminder" }));

    await waitFor(() =>
      expect(createReminder).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "New Reminder",
          templateId: "template-1",
        }),
      ),
    );

    await user.click(screen.getByRole("tab", { name: "Settings" }));
    const settingsSwitches = screen.getAllByRole("switch");
    await user.click(settingsSwitches[0]);
    await user.click(settingsSwitches[1]);
    await user.click(settingsSwitches[2]);

    expect(screen.getByPlaceholderText("ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Your SendGrid API key")).toBeInTheDocument();
    expect(screen.getByDisplayValue("24")).toBeInTheDocument();
    // The settings card is display-only: per-practice provider credentials
    // have no backend persistence yet, so the save affordance is honestly
    // labelled and disabled rather than faking a successful save.
    const saveSettingsBtn = screen.getByRole("button", { name: "Save Settings (unavailable)" });
    expect(saveSettingsBtn).toBeDisabled();
  });
});
