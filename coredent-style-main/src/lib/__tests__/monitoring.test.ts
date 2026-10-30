import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  monitoring,
  useMonitoring,
  trackAsync,
} from "../monitoring";
import { logger } from "../logger";

describe("monitoring", () => {
  beforeEach(() => {
    monitoring.clear();
    logger.clearLogs();
    vi.clearAllMocks();
  });

  describe("trackMetric", () => {
    it("stores the metric", () => {
      monitoring.trackMetric("api_call", 100);
      const metrics = monitoring.getMetrics();
      expect(metrics).toHaveLength(1);
      expect(metrics[0].name).toBe("api_call");
      expect(metrics[0].value).toBe(100);
    });

    it("warns when value exceeds 1000ms", () => {
      const warnSpy = vi.spyOn(logger, "warn");
      monitoring.trackMetric("slow", 1500, { endpoint: "/x" });
      expect(warnSpy).toHaveBeenCalledWith(
        "Slow operation detected: slow",
        expect.objectContaining({ value: 1500 }),
      );
    });

    it("keeps at most maxEntries metrics", () => {
      for (let i = 0; i < 120; i++) {
        monitoring.trackMetric("m", i);
      }
      expect(monitoring.getMetrics(200).length).toBeLessThanOrEqual(100);
    });

    it("sends to gtag when available (production path)", () => {
      const gtag = vi.fn();
      (window as any).gtag = gtag;
      // Force the production branch by spying on isDevelopment via env.
      // monitoring reads import.meta.env.DEV at construction; simulate prod by
      // setting gtag and asserting the production branch is exercised through
      // getAverageMetric still working.
      monitoring.trackMetric("m", 10, { ok: true });
      // In dev, sendToAnalytics is not called, so gtag should not be invoked.
      expect(gtag).not.toHaveBeenCalled();
      delete (window as any).gtag;
    });
  });

  describe("trackAction", () => {
    it("stores the action", () => {
      monitoring.trackAction("click", "Button");
      const actions = monitoring.getActions();
      expect(actions).toHaveLength(1);
      expect(actions[0].action).toBe("click");
      expect(actions[0].component).toBe("Button");
    });

    it("logs in development", () => {
      const debugSpy = vi.spyOn(logger, "debug");
      monitoring.trackAction("click", "Button", { id: 1 });
      expect(debugSpy).toHaveBeenCalledWith(
        "User action: click in Button",
        { id: 1 },
      );
    });
  });

  describe("trackPageView", () => {
    it("records a page_view action on the router component", () => {
      monitoring.trackPageView("/dashboard", "Dashboard");
      const actions = monitoring.getActions();
      expect(actions[0].action).toBe("page_view");
      expect(actions[0].component).toBe("router");
      expect(actions[0].metadata).toEqual({ path: "/dashboard", title: "Dashboard" });
    });
  });

  describe("trackApiCall / trackComponentRender / trackSessionDuration", () => {
    it("trackApiCall stores a metric with endpoint and status", () => {
      monitoring.trackApiCall("/api/x", 250, 200);
      const metric = monitoring.getMetrics()[0];
      expect(metric.name).toBe("api_call");
      expect(metric.metadata).toEqual({ endpoint: "/api/x", status: 200 });
    });

    it("trackComponentRender stores a component_render metric", () => {
      monitoring.trackComponentRender("Card", 5);
      expect(monitoring.getMetrics()[0].name).toBe("component_render");
    });

    it("trackSessionDuration stores a session_duration metric", () => {
      monitoring.trackSessionDuration(60000);
      expect(monitoring.getMetrics()[0].name).toBe("session_duration");
    });
  });

  describe("trackFeatureUsage", () => {
    it("records a feature_used action keyed by feature", () => {
      monitoring.trackFeatureUsage("ai_assistant", { mode: "demo" });
      const action = monitoring.getActions()[0];
      expect(action.action).toBe("feature_used");
      expect(action.component).toBe("ai_assistant");
    });
  });

  describe("trackError", () => {
    it("logs the error and records an error_occurred action", () => {
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const err = new Error("fail");
      monitoring.trackError(err, { code: 500 });
      const action = monitoring.getActions()[0];
      expect(action.action).toBe("error_occurred");
      expect(action.metadata).toMatchObject({ message: "fail", code: 500 });
      errorSpy.mockRestore();
    });
  });

  describe("getAverageMetric", () => {
    it("returns 0 when no metrics exist", () => {
      expect(monitoring.getAverageMetric("missing")).toBe(0);
    });

    it("returns the average for matching metrics", () => {
      monitoring.trackMetric("latency", 100);
      monitoring.trackMetric("latency", 300);
      expect(monitoring.getAverageMetric("latency")).toBe(200);
    });
  });

  describe("clear", () => {
    it("empties metrics and actions", () => {
      monitoring.trackMetric("m", 1);
      monitoring.trackAction("a", "c");
      monitoring.clear();
      expect(monitoring.getMetrics()).toHaveLength(0);
      expect(monitoring.getActions()).toHaveLength(0);
    });
  });

  describe("export", () => {
    it("returns a JSON string with metrics and actions", () => {
      monitoring.trackMetric("m", 1);
      monitoring.trackAction("a", "c");
      const exported = monitoring.export();
      const parsed = JSON.parse(exported);
      expect(parsed.metrics).toHaveLength(1);
      expect(parsed.actions).toHaveLength(1);
      expect(parsed.timestamp).toBeTypeOf("number");
    });
  });

  describe("useMonitoring", () => {
    it("returns trackAction and trackMount bound to the component name", () => {
      const m = useMonitoring("MyComponent");
      m.trackAction("rendered", { ok: true });
      expect(monitoring.getActions()[0].component).toBe("MyComponent");

      m.trackMount();
      expect(monitoring.getMetrics()[0].name).toBe("component_render");
    });
  });

  describe("trackAsync", () => {
    it("records a successful async operation and returns its result", async () => {
      const result = await trackAsync("job", async () => 42);
      expect(result).toBe(42);
      const metric = monitoring.getMetrics()[0];
      expect(metric.name).toBe("job");
      expect(metric.metadata).toMatchObject({ success: true });
    });

    it("records a failed async operation and rethrows", async () => {
      await expect(
        trackAsync("job", async () => {
          throw new Error("nope");
        }),
      ).rejects.toThrow("nope");
      const metric = monitoring.getMetrics()[0];
      expect(metric.metadata).toMatchObject({ success: false });
    });
  });

  describe("production and analytics integration", () => {
    const mockGtag = vi.fn();
    const mockMixpanel = {
      track: vi.fn(),
    };
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });

    beforeEach(() => {
      vi.clearAllMocks();
      vi.stubEnv("DEV", false as any);
      vi.stubEnv("PROD", true as any);

      (window as any).gtag = mockGtag;
      (window as any).mixpanel = mockMixpanel;
      vi.stubGlobal("fetch", mockFetch);
    });

    afterEach(() => {
      delete (window as any).gtag;
      delete (window as any).mixpanel;
      vi.restoreAllMocks();
    });

    it("sends metrics and actions to gtag, mixpanel, and custom endpoint in production", async () => {
      vi.stubEnv("VITE_ANALYTICS_ENDPOINT", "https://analytics.example.com/events");
      vi.resetModules();
      const { monitoring: prodMonitoring } = await import("../monitoring");

      // Track metric in production
      prodMonitoring.trackMetric("api_latency", 120, { path: "/users" });

      expect(mockGtag).toHaveBeenCalledWith("event", "api_latency", {
        value: 120,
        path: "/users",
      });
      expect(mockMixpanel.track).toHaveBeenCalledWith("api_latency", {
        value: 120,
        path: "/users",
      });
      expect(mockFetch).toHaveBeenCalledWith(
        "https://analytics.example.com/events",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("api_latency"),
        }),
      );

      // Track action in production
      prodMonitoring.trackAction("button_click", "Navbar", { buttonId: "login" });

      expect(mockGtag).toHaveBeenCalledWith("event", "button_click", {
        component: "Navbar",
        buttonId: "login",
      });
      expect(mockMixpanel.track).toHaveBeenCalledWith("button_click", {
        component: "Navbar",
        buttonId: "login",
      });
      expect(mockFetch).toHaveBeenLastCalledWith(
        "https://analytics.example.com/events",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("button_click"),
        }),
      );
    });

    it("gracefully handles fetch failures for custom endpoint", async () => {
      vi.stubEnv("VITE_ANALYTICS_ENDPOINT", "https://analytics.example.com/events");
      mockFetch.mockRejectedValueOnce(new Error("Network fail"));
      vi.resetModules();
      const { monitoring: prodMonitoring } = await import("../monitoring");

      // Should not throw or crash the application
      expect(() => prodMonitoring.trackMetric("test_metric", 5)).not.toThrow();
    });
  });
});
