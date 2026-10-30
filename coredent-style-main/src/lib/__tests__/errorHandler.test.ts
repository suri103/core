import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setupGlobalErrorHandlers } from "../errorHandler";
import { logger } from "../logger";

describe("errorHandler", () => {
  beforeEach(() => {
    logger.clearLogs();
  });

  afterEach(() => {
    // reset global handlers so they don't leak into other tests
    window.onerror = null;
    window.onunhandledrejection = null;
  });

  it("installs window.onerror and window.onunhandledrejection handlers", () => {
    setupGlobalErrorHandlers();
    expect(typeof window.onerror).toBe("function");
    expect(typeof window.onunhandledrejection).toBe("function");
  });

  it("logs errors thrown via window.onerror", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    setupGlobalErrorHandlers();
    const err = new Error("boom");
    // call the handler directly rather than relying on native event dispatch
    const result = window.onerror!("message", "source.js", 10, 20, err);
    const recent = logger.getRecentLogs();
    expect(recent[0].level).toBe("error");
    expect(recent[0].error).toBe(err);
    expect(recent[0].context).toEqual({
      source: "source.js",
      lineno: 10,
      colno: 20,
    });
    expect(result).toBe(false);
    errorSpy.mockRestore();
  });

  it("creates an Error when window.onerror is called without one", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    setupGlobalErrorHandlers();
    window.onerror!("message", "source.js", 1, 2, undefined);
    const recent = logger.getRecentLogs();
    expect(recent[0].error).toBeInstanceOf(Error);
    expect(recent[0].error!.message).toBe("message");
    errorSpy.mockRestore();
  });

  it("logs unhandled promise rejections", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    setupGlobalErrorHandlers();
    const err = new Error("async fail");
    window.onunhandledrejection!({ reason: err } as PromiseRejectionEvent);
    const recent = logger.getRecentLogs();
    expect(recent[0].level).toBe("error");
    expect(recent[0].error).toBe(err);
    errorSpy.mockRestore();
  });

  it("wraps non-Error rejection reasons in an Error", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    setupGlobalErrorHandlers();
    window.onunhandledrejection!({ reason: "string reason" } as PromiseRejectionEvent);
    const recent = logger.getRecentLogs();
    expect(recent[0].error).toBeInstanceOf(Error);
    expect(recent[0].error!.message).toBe("string reason");
    errorSpy.mockRestore();
  });
});
