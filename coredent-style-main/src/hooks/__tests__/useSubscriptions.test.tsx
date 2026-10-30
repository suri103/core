import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/hooks/use-toast";
import { subscriptionApi, subscriptionPlanApi } from "@/services/subscriptionsApi";
import {
  subscriptionKeys,
  useCancelSubscription,
  useChangePlan,
  useCreateSubscription,
  useDunningEvents,
  useInvoiceHistory,
  usePauseSubscription,
  useRecordUsage,
  useResumeSubscription,
  useSubscription,
  useSubscriptionPlan,
  useSubscriptionPlans,
  useSubscriptions,
  useSubscriptionStats,
  useSubscriptionUsage,
  useTrial,
} from "../useSubscriptions";

vi.mock("@/hooks/use-toast", () => ({
  toast: vi.fn(),
}));

vi.mock("@/services/subscriptionsApi", () => ({
  subscriptionPlanApi: {
    list: vi.fn(),
    getById: vi.fn(),
  },
  subscriptionApi: {
    list: vi.fn(),
    getById: vi.fn(),
    getUsage: vi.fn(),
    getDunningEvents: vi.fn(),
    getStats: vi.fn(),
    getInvoiceHistory: vi.fn(),
    getTrial: vi.fn(),
    create: vi.fn(),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    changePlan: vi.fn(),
    recordUsage: vi.fn(),
  },
}));

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useSubscriptions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("builds stable query keys for all subscription resources", () => {
    expect(subscriptionKeys.plans()).toEqual(["subscriptions", "plans"]);
    expect(subscriptionKeys.plan("plan-1")).toEqual(["subscriptions", "plans", "plan-1"]);
    expect(subscriptionKeys.list({ status: "active" })).toEqual([
      "subscriptions",
      "list",
      { status: "active" },
    ]);
    expect(subscriptionKeys.detail("sub-1")).toEqual(["subscriptions", "sub-1"]);
    expect(subscriptionKeys.usage("sub-1")).toEqual(["subscriptions", "sub-1", "usage"]);
    expect(subscriptionKeys.dunning("sub-1")).toEqual(["subscriptions", "sub-1", "dunning"]);
    expect(subscriptionKeys.stats()).toEqual(["subscriptions", "stats"]);
    expect(subscriptionKeys.invoices("sub-1")).toEqual(["subscriptions", "sub-1", "invoices"]);
    expect(subscriptionKeys.trial("sub-1")).toEqual(["subscriptions", "sub-1", "trial"]);
  });

  it("loads every subscription query with the expected service arguments", async () => {
    vi.mocked(subscriptionPlanApi.list).mockResolvedValue({ success: true, data: [{ id: "plan-1" }] } as never);
    vi.mocked(subscriptionPlanApi.getById).mockResolvedValue({ success: true, data: { id: "plan-1" } } as never);
    vi.mocked(subscriptionApi.list).mockResolvedValue({ success: true, data: [{ id: "sub-1" }] } as never);
    vi.mocked(subscriptionApi.getById).mockResolvedValue({ success: true, data: { id: "sub-1" } } as never);
    vi.mocked(subscriptionApi.getUsage).mockResolvedValue({ success: true, data: { units: 4 } } as never);
    vi.mocked(subscriptionApi.getDunningEvents).mockResolvedValue({ success: true, data: [{ id: "event-1" }] } as never);
    vi.mocked(subscriptionApi.getStats).mockResolvedValue({ success: true, data: { active: 1 } } as never);
    vi.mocked(subscriptionApi.getInvoiceHistory).mockResolvedValue({ success: true, data: [{ id: "invoice-1" }] } as never);
    vi.mocked(subscriptionApi.getTrial).mockResolvedValue({ success: true, data: { active: true } } as never);

    const wrapper = createWrapper();

    const plans = renderHook(() => useSubscriptionPlans(false), { wrapper });
    const plan = renderHook(() => useSubscriptionPlan("plan-1"), { wrapper });
    const subscriptions = renderHook(
      () => useSubscriptions({ page: 2, limit: 25, status: "active" }),
      { wrapper },
    );
    const subscription = renderHook(() => useSubscription("sub-1"), { wrapper });
    const usage = renderHook(() => useSubscriptionUsage("sub-1"), { wrapper });
    const dunning = renderHook(() => useDunningEvents("sub-1"), { wrapper });
    const stats = renderHook(() => useSubscriptionStats(), { wrapper });
    const invoices = renderHook(() => useInvoiceHistory("sub-1"), { wrapper });
    const trial = renderHook(() => useTrial("sub-1"), { wrapper });

    await waitFor(() => {
      expect(plans.result.current.isSuccess).toBe(true);
      expect(plan.result.current.isSuccess).toBe(true);
      expect(subscriptions.result.current.isSuccess).toBe(true);
      expect(subscription.result.current.isSuccess).toBe(true);
      expect(usage.result.current.isSuccess).toBe(true);
      expect(dunning.result.current.isSuccess).toBe(true);
      expect(stats.result.current.isSuccess).toBe(true);
      expect(invoices.result.current.isSuccess).toBe(true);
      expect(trial.result.current.isSuccess).toBe(true);
    });

    expect(subscriptionPlanApi.list).toHaveBeenCalledWith(false);
    expect(subscriptionPlanApi.getById).toHaveBeenCalledWith("plan-1");
    expect(subscriptionApi.list).toHaveBeenCalledWith(2, 25, "active");
    expect(subscriptionApi.getById).toHaveBeenCalledWith("sub-1");
    expect(subscriptionApi.getUsage).toHaveBeenCalledWith("sub-1");
    expect(subscriptionApi.getDunningEvents).toHaveBeenCalledWith("sub-1");
    expect(subscriptionApi.getStats).toHaveBeenCalledOnce();
    expect(subscriptionApi.getInvoiceHistory).toHaveBeenCalledWith("sub-1");
    expect(subscriptionApi.getTrial).toHaveBeenCalledWith("sub-1");
  });

  it("does not call detail queries when they are disabled or missing an id", () => {
    const wrapper = createWrapper();

    renderHook(() => useSubscriptionPlan("", true), { wrapper });
    renderHook(() => useSubscription("sub-1", false), { wrapper });
    renderHook(() => useSubscriptionUsage("", true), { wrapper });
    renderHook(() => useDunningEvents("sub-1", false), { wrapper });
    renderHook(() => useSubscriptionStats(false), { wrapper });
    renderHook(() => useInvoiceHistory("", true), { wrapper });
    renderHook(() => useTrial("sub-1", false), { wrapper });

    expect(subscriptionPlanApi.getById).not.toHaveBeenCalled();
    expect(subscriptionApi.getById).not.toHaveBeenCalled();
    expect(subscriptionApi.getUsage).not.toHaveBeenCalled();
    expect(subscriptionApi.getDunningEvents).not.toHaveBeenCalled();
    expect(subscriptionApi.getStats).not.toHaveBeenCalled();
    expect(subscriptionApi.getInvoiceHistory).not.toHaveBeenCalled();
    expect(subscriptionApi.getTrial).not.toHaveBeenCalled();
  });

  it("runs subscription mutations, invalidates data, and calls success callbacks", async () => {
    vi.mocked(subscriptionApi.create).mockResolvedValue({ success: true, data: { id: "sub-created" } } as never);
    vi.mocked(subscriptionApi.cancel).mockResolvedValue({ success: true, data: { id: "sub-cancelled" } } as never);
    vi.mocked(subscriptionApi.pause).mockResolvedValue({ success: true, data: { id: "sub-paused" } } as never);
    vi.mocked(subscriptionApi.resume).mockResolvedValue({ success: true, data: { id: "sub-resumed" } } as never);
    vi.mocked(subscriptionApi.changePlan).mockResolvedValue({ success: true, data: { id: "sub-changed" } } as never);
    vi.mocked(subscriptionApi.recordUsage).mockResolvedValue({ success: true, data: { id: "usage-1" } } as never);

    const onSuccess = vi.fn();
    const wrapper = createWrapper();

    const create = renderHook(() => useCreateSubscription(onSuccess), { wrapper });
    const cancel = renderHook(() => useCancelSubscription(onSuccess), { wrapper });
    const pause = renderHook(() => usePauseSubscription(onSuccess), { wrapper });
    const resume = renderHook(() => useResumeSubscription(onSuccess), { wrapper });
    const changePlan = renderHook(() => useChangePlan(onSuccess), { wrapper });
    const recordUsage = renderHook(() => useRecordUsage(onSuccess), { wrapper });

    await act(async () => {
      await create.result.current.mutateAsync({ plan_id: "plan-1" } as never);
      await cancel.result.current.mutateAsync({
        id: "sub-1",
        data: { cancel_at_period_end: true, reason: "closing" },
      });
      await pause.result.current.mutateAsync({
        id: "sub-1",
        data: { paused_until: "2026-07-01", reason: "vacation" },
      });
      await resume.result.current.mutateAsync("sub-1");
      await changePlan.result.current.mutateAsync({
        id: "sub-1",
        data: { new_plan_id: "plan-2", proration_behavior: "create_prorations" },
      });
      await recordUsage.result.current.mutateAsync({
        id: "sub-1",
        data: { quantity: "4", description: "SMS bundle" },
      });
    });

    expect(subscriptionApi.create).toHaveBeenCalledWith({ plan_id: "plan-1" }, expect.any(Object));
    expect(subscriptionApi.cancel).toHaveBeenCalledWith("sub-1", {
      cancel_at_period_end: true,
      reason: "closing",
    });
    expect(subscriptionApi.pause).toHaveBeenCalledWith("sub-1", {
      paused_until: "2026-07-01",
      reason: "vacation",
    });
    expect(subscriptionApi.resume).toHaveBeenCalledWith("sub-1", expect.any(Object));
    expect(subscriptionApi.changePlan).toHaveBeenCalledWith("sub-1", {
      new_plan_id: "plan-2",
      proration_behavior: "create_prorations",
    });
    expect(subscriptionApi.recordUsage).toHaveBeenCalledWith("sub-1", {
      quantity: "4",
      description: "SMS bundle",
    });
    expect(onSuccess).toHaveBeenCalledTimes(6);
    expect(toast).toHaveBeenCalledWith({ title: "Subscription activated successfully" });
    expect(toast).toHaveBeenCalledWith({ title: "Subscription cancelled" });
    expect(toast).toHaveBeenCalledWith({ title: "Subscription paused" });
    expect(toast).toHaveBeenCalledWith({ title: "Subscription resumed" });
    expect(toast).toHaveBeenCalledWith({ title: "Plan changed successfully" });
    expect(toast).toHaveBeenCalledWith({ title: "Usage recorded" });
  });

  it("shows destructive toasts for every failed subscription mutation", async () => {
    vi.mocked(subscriptionApi.create).mockRejectedValue(new Error("create failed"));
    vi.mocked(subscriptionApi.cancel).mockRejectedValue(new Error("cancel failed"));
    vi.mocked(subscriptionApi.pause).mockRejectedValue(new Error("pause failed"));
    vi.mocked(subscriptionApi.resume).mockRejectedValue(new Error("resume failed"));
    vi.mocked(subscriptionApi.changePlan).mockRejectedValue(new Error("change failed"));
    vi.mocked(subscriptionApi.recordUsage).mockRejectedValue(new Error("usage failed"));

    const wrapper = createWrapper();

    const create = renderHook(() => useCreateSubscription(), { wrapper });
    const cancel = renderHook(() => useCancelSubscription(), { wrapper });
    const pause = renderHook(() => usePauseSubscription(), { wrapper });
    const resume = renderHook(() => useResumeSubscription(), { wrapper });
    const changePlan = renderHook(() => useChangePlan(), { wrapper });
    const recordUsage = renderHook(() => useRecordUsage(), { wrapper });

    await act(async () => {
      await expect(create.result.current.mutateAsync({ plan_id: "plan-1" } as never)).rejects.toThrow(
        "create failed",
      );
      await expect(
        cancel.result.current.mutateAsync({ id: "sub-1", data: { reason: "closing" } }),
      ).rejects.toThrow("cancel failed");
      await expect(
        pause.result.current.mutateAsync({ id: "sub-1", data: { reason: "vacation" } }),
      ).rejects.toThrow("pause failed");
      await expect(resume.result.current.mutateAsync("sub-1")).rejects.toThrow("resume failed");
      await expect(
        changePlan.result.current.mutateAsync({ id: "sub-1", data: { new_plan_id: "plan-2" } }),
      ).rejects.toThrow("change failed");
      await expect(
        recordUsage.result.current.mutateAsync({ id: "sub-1", data: { quantity: "4" } }),
      ).rejects.toThrow("usage failed");
    });

    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to activate subscription",
      description: "create failed",
    });
    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to cancel subscription",
      description: "cancel failed",
    });
    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to pause subscription",
      description: "pause failed",
    });
    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to resume subscription",
      description: "resume failed",
    });
    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to change plan",
      description: "change failed",
    });
    expect(toast).toHaveBeenCalledWith({
      variant: "destructive",
      title: "Failed to record usage",
      description: "usage failed",
    });
  });
});
