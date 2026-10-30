import { describe, it, expect, vi, beforeEach } from "vitest";

// Capture the metric callback registered by each web-vitals subscriber so tests
// can invoke them with synthetic Metric objects.
const captured: Record<string, (m: any) => void> = {};

vi.mock("web-vitals", () => ({
  onCLS: (cb: (m: any) => void) => {
    captured.CLS = cb;
  },
  onFID: (cb: (m: any) => void) => {
    captured.FID = cb;
  },
  onFCP: (cb: (m: any) => void) => {
    captured.FCP = cb;
  },
  onLCP: (cb: (m: any) => void) => {
    captured.LCP = cb;
  },
  onTTFB: (cb: (m: any) => void) => {
    captured.TTFB = cb;
  },
}));

import { initWebVitals, trackCustomMetric } from "../webVitals";
import { logger } from "../logger";

describe("webVitals", () => {
  beforeEach(() => {
    logger.clearLogs();
    vi.clearAllMocks();
  });

  function makeMetric(name: string, value: number, delta = 1) {
    return {
      name,
      value,
      delta,
      id: `${name}-id`,
      rating: "good" as const,
      entries: [],
    };
  }

  it("registers subscribers for each web vital", () => {
    initWebVitals();
    expect(captured.CLS).toBeTypeOf("function");
    expect(captured.FID).toBeTypeOf("function");
    expect(captured.FCP).toBeTypeOf("function");
    expect(captured.LCP).toBeTypeOf("function");
    expect(captured.TTFB).toBeTypeOf("function");
  });

  it("reports a 'good' rating when value is below the good threshold", () => {
    const debugSpy = vi.spyOn(logger, "debug");
    const infoSpy = vi.spyOn(logger, "info");
    initWebVitals();
    captured.LCP!(makeMetric("LCP", 1000));
    expect(infoSpy).toHaveBeenCalledWith(
      "Web Vital: LCP",
      expect.objectContaining({ rating: "good", value: 1000 }),
    );
    expect(debugSpy).toHaveBeenCalled();
  });

  it("reports 'needs-improvement' between good and poor thresholds", () => {
    vi.spyOn(logger, "info");
    initWebVitals();
    captured.FCP!(makeMetric("FCP", 2000));
    expect(logger.getRecentLogs()[0].context).toMatchObject({
      rating: "needs-improvement",
    });
  });

  it("reports 'poor' above the poor threshold", () => {
    initWebVitals();
    captured.TTFB!(makeMetric("TTFB", 5000));
    expect(logger.getRecentLogs()[0].context).toMatchObject({
      rating: "poor",
    });
  });

  it("defaults to 'good' for an unknown metric name", () => {
    initWebVitals();
    captured.CLS!(makeMetric("UNKNOWN", 9999));
    expect(logger.getRecentLogs()[0].context).toMatchObject({
      rating: "good",
    });
  });

  it("sends the metric to gtag when available", () => {
    const gtag = vi.fn();
    (window as any).gtag = gtag;
    initWebVitals();
    captured.CLS!(makeMetric("CLS", 0.05, 0.05));
    expect(gtag).toHaveBeenCalledWith(
      "event",
      "CLS",
      expect.objectContaining({ value: Math.round(0.05 * 1000) }),
    );
    delete (window as any).gtag;
  });

  describe("trackCustomMetric", () => {
    it("logs the custom metric and sends it to gtag when available", () => {
      const gtag = vi.fn();
      (window as any).gtag = gtag;
      trackCustomMetric("custom", 42);
      expect(logger.getRecentLogs()[0].message).toBe("Custom Metric: custom");
      expect(gtag).toHaveBeenCalledWith(
        "event",
        "custom_metric",
        expect.objectContaining({ value: 42 }),
      );
      delete (window as any).gtag;
    });

    it("works without gtag present", () => {
      expect(() => trackCustomMetric("custom", 42)).not.toThrow();
      expect(logger.getRecentLogs()[0].context).toMatchObject({
        metric: "custom",
        value: 42,
      });
    });
  });
});
