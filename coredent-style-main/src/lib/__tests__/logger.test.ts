import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  logger,
  logError,
  logApiError,
  logPerformance,
} from "../logger";

const mockSentry = vi.hoisted(() => ({
  init: vi.fn(),
  captureException: vi.fn(),
  captureMessage: vi.fn(),
}));

vi.mock("@sentry/browser", () => mockSentry);

describe("logger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    logger.clearLogs();
  });

  it("debug stores a log entry and logs to console in development", () => {
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
    logger.debug("debug message", { foo: 1 });
    const recent = logger.getRecentLogs();
    expect(recent).toHaveLength(1);
    expect(recent[0].level).toBe("debug");
    expect(recent[0].message).toBe("debug message");
    expect(recent[0].context).toEqual({ foo: 1 });
    expect(debugSpy).toHaveBeenCalled();
  });

  it("info stores a log entry", () => {
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    logger.info("info message", { bar: 2 });
    const recent = logger.getRecentLogs();
    expect(recent).toHaveLength(1);
    expect(recent[0].level).toBe("info");
    expect(infoSpy).toHaveBeenCalled();
  });

  it("warn stores a log entry and calls console.warn", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    logger.warn("warn message");
    const recent = logger.getRecentLogs();
    expect(recent).toHaveLength(1);
    expect(recent[0].level).toBe("warn");
    expect(warnSpy).toHaveBeenCalled();
  });

  it("error stores a log entry with the attached error", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const err = new Error("boom");
    logger.error("error message", err, { code: 500 });
    const recent = logger.getRecentLogs();
    expect(recent).toHaveLength(1);
    expect(recent[0].level).toBe("error");
    expect(recent[0].error).toBe(err);
    expect(recent[0].context).toEqual({ code: 500 });
    expect(errorSpy).toHaveBeenCalled();
  });

  it("getRecentLogs returns only the requested count", () => {
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
    vi.spyOn(console, "info").mockImplementation(() => {});
    for (let i = 0; i < 10; i++) {
      logger.info(`msg-${i}`);
    }
    expect(logger.getRecentLogs(3)).toHaveLength(3);
    expect(logger.getRecentLogs(3)[2].message).toBe("msg-9");
    // debug spy declared for parity but not asserted here
    expect(debugSpy).not.toHaveBeenCalled();
  });

  it("keeps only the most recent maxLogs entries", () => {
    vi.spyOn(console, "info").mockImplementation(() => {});
    for (let i = 0; i < 120; i++) {
      logger.info(`msg-${i}`);
    }
    const recent = logger.getRecentLogs(200);
    expect(recent.length).toBeLessThanOrEqual(100);
    expect(recent[0].message).toBe("msg-20");
  });

  it("clearLogs empties the stored logs", () => {
    vi.spyOn(console, "info").mockImplementation(() => {});
    logger.info("msg");
    expect(logger.getRecentLogs()).toHaveLength(1);
    logger.clearLogs();
    expect(logger.getRecentLogs()).toHaveLength(0);
  });

  it("exportLogs returns a JSON string of the stored logs", () => {
    vi.spyOn(console, "info").mockImplementation(() => {});
    logger.info("msg", { a: 1 });
    const exported = logger.exportLogs();
    const parsed = JSON.parse(exported);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].message).toBe("msg");
  });

  describe("helpers", () => {
    it("logError logs a React error boundary error", () => {
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const err = new Error("boundary");
      logError(err, { componentStack: "at SomeComponent" });
      const recent = logger.getRecentLogs();
      expect(recent[0].level).toBe("error");
      expect(recent[0].error).toBe(err);
      expect(recent[0].context).toEqual({ componentStack: "at SomeComponent" });
      expect(errorSpy).toHaveBeenCalled();
    });

    it("logApiError logs an API error with the endpoint", () => {
      vi.spyOn(console, "error").mockImplementation(() => {});
      const err = new Error("network");
      logApiError("/api/patients", err, { status: 500 });
      const recent = logger.getRecentLogs();
      expect(recent[0].message).toBe("API Error: /api/patients");
      expect(recent[0].context).toEqual({ endpoint: "/api/patients", status: 500 });
    });

    it("logPerformance logs a performance metric", () => {
      vi.spyOn(console, "info").mockImplementation(() => {});
      logPerformance("api_call", 250);
      const recent = logger.getRecentLogs();
      expect(recent[0].message).toBe("Performance: api_call");
      expect(recent[0].context).toEqual({ duration: 250, metric: "api_call" });
    });
  });

  describe("production and Sentry monitoring", () => {
    beforeEach(() => {
      vi.clearAllMocks();
      vi.stubEnv("DEV", false as any);
      vi.stubEnv("PROD", true as any);
    });

    it("initializes Sentry and scrubs sensitive headers in beforeSend", async () => {
      vi.stubEnv("VITE_SENTRY_DSN", "https://12345@o123.ingest.sentry.io/123");

      vi.resetModules();
      await import("../logger");

      expect(mockSentry.init).toHaveBeenCalled();
      const initConfig = mockSentry.init.mock.calls[0][0];

      // Test beforeSend scrubbing
      const dummyEvent = {
        request: {
          cookies: { session: "123" },
          headers: {
            Authorization: "Bearer token",
            cookie: "session=123",
            "x-csrf-token": "csrf123",
            "content-type": "application/json",
          },
        },
      };

      const scrubbed = initConfig.beforeSend(dummyEvent);
      expect(scrubbed.request.cookies).toBeUndefined();
      expect(scrubbed.request.headers.Authorization).toBeUndefined();
      expect(scrubbed.request.headers.cookie).toBeUndefined();
      expect(scrubbed.request.headers["x-csrf-token"]).toBeUndefined();
      expect(scrubbed.request.headers["content-type"]).toBe("application/json");
    });

    it("sends warnings and errors to Sentry", async () => {
      vi.stubEnv("VITE_SENTRY_DSN", "https://12345@o123.ingest.sentry.io/123");
      vi.resetModules();
      const { logger: prodLogger } = await import("../logger");

      vi.spyOn(console, "warn").mockImplementation(() => {});
      vi.spyOn(console, "error").mockImplementation(() => {});

      prodLogger.warn("some warning");
      expect(mockSentry.captureMessage).toHaveBeenCalledWith("some warning", "warning");

      const err = new Error("prod failure");
      prodLogger.error("some error", err);
      expect(mockSentry.captureException).toHaveBeenCalledWith(err);
    });

    it("does not initialize Sentry if DSN is invalid or placeholder", async () => {
      vi.stubEnv("VITE_SENTRY_DSN", "your-sentry-dsn");
      vi.resetModules();
      await import("../logger");
      expect(mockSentry.init).not.toHaveBeenCalled();
    });
  });
});
