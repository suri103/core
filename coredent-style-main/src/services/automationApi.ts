import { apiClient } from "./api";
import { requireApiData, requireApiSuccess } from "./apiResponse";
import type {
  AutomationEvent,
  AutomationPayload,
  AutomationWebhook,
} from "@/types/automation";

export const automationApi = {
  getWebhooks: async (): Promise<AutomationWebhook[]> =>
    requireApiData(
      await apiClient.get<AutomationWebhook[]>("/automations/webhooks"),
      "Failed to load automation webhooks",
    ),

  getWebhooksByEvent: async (
    event: AutomationEvent,
  ): Promise<AutomationWebhook[]> =>
    requireApiData(
      await apiClient.get<AutomationWebhook[]>("/automations/webhooks", { event }),
      "Failed to load automation webhooks",
    ),

  createWebhook: async (
    data: Omit<AutomationWebhook, "id" | "createdAt" | "updatedAt">,
  ): Promise<AutomationWebhook> =>
    requireApiData(
      await apiClient.post<AutomationWebhook>("/automations/webhooks", data),
      "Failed to create webhook",
    ),

  updateWebhook: async (
    id: string,
    data: Partial<AutomationWebhook>,
  ): Promise<AutomationWebhook> =>
    requireApiData(
      await apiClient.put<AutomationWebhook>(`/automations/webhooks/${id}`, data),
      "Failed to update webhook",
    ),

  deleteWebhook: async (id: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete<void>(`/automations/webhooks/${id}`),
      "Failed to delete webhook",
    );
  },

  toggleWebhook: async (id: string): Promise<AutomationWebhook> =>
    requireApiData(
      await apiClient.post<AutomationWebhook>(`/automations/webhooks/${id}/toggle`),
      "Failed to toggle webhook",
    ),

  triggerWebhook: async (
    event: AutomationEvent,
    payload: AutomationPayload,
  ): Promise<{ success: boolean; triggeredCount: number }> =>
    requireApiData(
      await apiClient.post<{ success: boolean; triggeredCount: number }>(
        "/automations/trigger",
        { event, payload },
      ),
      "Failed to trigger automation",
    ),

  testWebhook: async (
    webhookUrl: string,
    secretToken?: string,
  ): Promise<boolean> =>
    requireApiData(
      await apiClient.post<{ success: boolean }>("/automations/test", {
        webhookUrl,
        secretToken,
      }),
      "Failed to test webhook",
    ).success,
};

export async function triggerAutomation(
  event: AutomationEvent,
  payload: AutomationPayload,
): Promise<void> {
  await automationApi.triggerWebhook(event, payload);
}