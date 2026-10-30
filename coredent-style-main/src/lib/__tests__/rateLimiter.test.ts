import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  apiRateLimiter,
  searchRateLimiter,
  authRateLimiter,
  debounce,
  throttle,
} from "../rateLimiter";

function isRateLimiter(obj: unknown): boolean {
  return (
    !!obj &&
    typeof (obj as any).check === "function" &&
    typeof (obj as any).reset === "function" &&
    typeof (obj as any).resetAll === "function" &&
    typeof (obj as any).destroy === "function"
  );
}

describe("RateLimiter (via authRateLimiter singleton)", () => {
  // authRateLimiter: 5 requests per 5 minutes (300000ms)
  beforeEach(() => {
    vi.useFakeTimers();
    authRateLimiter.resetAll();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("allows requests up to the limit", () => {
    const first = authRateLimiter.check("key");
    expect(first.allowed).toBe(true);
    expect(first.remaining).toBe(4);

    const second = authRateLimiter.check("key");
    expect(second.allowed).toBe(true);
    expect(second.remaining).toBe(3);
  });

  it("blocks requests once the limit is reached", () => {
    for (let i = 0; i < 5; i++) authRateLimiter.check("key");
    const blocked = authRateLimiter.check("key");
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
  });

  it("resets after the window elapses", () => {
    for (let i = 0; i < 5; i++) authRateLimiter.check("key");
    expect(authRateLimiter.check("key").allowed).toBe(false);

    vi.advanceTimersByTime(300001);

    const after = authRateLimiter.check("key");
    expect(after.allowed).toBe(true);
    expect(after.remaining).toBe(4);
  });

  it("tracks keys independently", () => {
    authRateLimiter.check("a");
    authRateLimiter.check("a");
    const b = authRateLimiter.check("b");
    expect(b.allowed).toBe(true);
    expect(b.remaining).toBe(4);
  });

  it("reset removes a single key", () => {
    authRateLimiter.check("a");
    authRateLimiter.check("a");
    authRateLimiter.reset("a");
    const after = authRateLimiter.check("a");
    expect(after.remaining).toBe(4);
  });

  it("resetAll clears all keys", () => {
    authRateLimiter.check("a");
    authRateLimiter.check("b");
    authRateLimiter.resetAll();
    const after = authRateLimiter.check("a");
    expect(after.remaining).toBe(4);
  });

  it("destroy clears entries and stops the cleanup interval", () => {
    authRateLimiter.check("a");
    authRateLimiter.destroy();
    const after = authRateLimiter.check("a");
    expect(after.remaining).toBe(4);
  });

  it("warns when the rate limit is exceeded", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (let i = 0; i < 5; i++) authRateLimiter.check("key");
    authRateLimiter.check("key");
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining("Rate limit exceeded"),
      expect.objectContaining({ key: "key" }),
    );
    vi.restoreAllMocks();
  });
});

describe("rate limiter singletons", () => {
  it("exports pre-configured limiters with the expected API", () => {
    expect(isRateLimiter(apiRateLimiter)).toBe(true);
    expect(isRateLimiter(searchRateLimiter)).toBe(true);
    expect(isRateLimiter(authRateLimiter)).toBe(true);
  });

  it("apiRateLimiter allows up to 100 requests per window", () => {
    const first = apiRateLimiter.check("singleton-api");
    expect(first.allowed).toBe(true);
    expect(first.remaining).toBe(99);
  });

  it("searchRateLimiter allows up to 30 requests per window", () => {
    const first = searchRateLimiter.check("singleton-search");
    expect(first.allowed).toBe(true);
    expect(first.remaining).toBe(29);
  });
});

describe("debounce / throttle helpers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounce only fires the last call after the wait", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(101);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("throttle fires immediately then suppresses until the limit elapses", () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);
    throttled();
    throttled();
    throttled();
    expect(fn).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(101);
    throttled();
    expect(fn).toHaveBeenCalledTimes(2);
  });
});
