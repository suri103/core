import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useFormatters } from "../useFormatters";

describe("useFormatters", () => {
  it("returns formatCurrency function", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatCurrency).toBeDefined();
    expect(typeof result.current.formatCurrency).toBe("function");
  });

  it("returns formatAppointmentType function", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatAppointmentType).toBeDefined();
    expect(typeof result.current.formatAppointmentType).toBe("function");
  });

  it("returns formatDate function", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatDate).toBeDefined();
    expect(typeof result.current.formatDate).toBe("function");
  });

  it("returns formatTime function", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatTime).toBeDefined();
    expect(typeof result.current.formatTime).toBe("function");
  });

  it("formats currency correctly", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatCurrency(100)).toBe("$100");
    expect(result.current.formatCurrency(99.99)).toBe("$100");
    expect(result.current.formatCurrency(0)).toBe("$0");
  });

  it("formats appointment type correctly", () => {
    const { result } = renderHook(() => useFormatters());
    expect(result.current.formatAppointmentType("root_canal")).toBe("Root Canal");
    expect(result.current.formatAppointmentType("cleaning")).toBe("Cleaning");
    expect(result.current.formatAppointmentType("")).toBe("");
  });

  it("formats date correctly", () => {
    const { result } = renderHook(() => useFormatters());
    const date = new Date("2026-05-10");
    const formatted = result.current.formatDate(date);
    expect(formatted).toContain("2026");
    expect(formatted).toContain("May");
  });

  it("formats date from string", () => {
    const { result } = renderHook(() => useFormatters());
    const formatted = result.current.formatDate("2026-05-10");
    expect(formatted).toContain("2026");
  });

  it("formats time correctly", () => {
    const { result } = renderHook(() => useFormatters());
    const date = new Date("2026-05-10T14:30:00");
    const formatted = result.current.formatTime(date);
    expect(formatted).toContain("2");
    expect(formatted).toContain("30");
  });

  it("formats time from string", () => {
    const { result } = renderHook(() => useFormatters());
    const formatted = result.current.formatTime("2026-05-10T09:15:00");
    expect(formatted).toContain("9");
    expect(formatted).toContain("15");
  });
});
