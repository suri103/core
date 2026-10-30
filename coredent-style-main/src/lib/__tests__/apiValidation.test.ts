import { describe, it, expect, vi, beforeEach } from "vitest";
import { z } from "zod";
import {
  validateApiResponse,
  validateApiResponseStrict,
  sanitizeInput,
  isValidEmail,
  isValidPhone,
  isValidUrl,
  isSafeInteger,
  isValidISODate,
} from "../apiValidation";

describe("apiValidation", () => {
  const schema = z.object({ id: z.number(), name: z.string() });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("validateApiResponse", () => {
    it("returns parsed data when valid", () => {
      const result = validateApiResponse(
        { id: 1, name: "test" },
        schema,
        "/api/test",
      );
      expect(result).toEqual({ id: 1, name: "test" });
    });

    it("returns null and logs when invalid", () => {
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const result = validateApiResponse(
        { id: "not-a-number" },
        schema,
        "/api/test",
      );
      expect(result).toBeNull();
      errorSpy.mockRestore();
    });
  });

  describe("validateApiResponseStrict", () => {
    it("returns parsed data when valid", () => {
      const result = validateApiResponseStrict(
        { id: 1, name: "test" },
        schema,
        "/api/test",
      );
      expect(result).toEqual({ id: 1, name: "test" });
    });

    it("throws when invalid", () => {
      vi.spyOn(console, "error").mockImplementation(() => {});
      expect(() =>
        validateApiResponseStrict({ id: "x" }, schema, "/api/test"),
      ).toThrow("Invalid API response from /api/test");
    });
  });

  describe("sanitizeInput", () => {
    it("escapes HTML special characters", () => {
      const result = sanitizeInput(`<script>"hi" & '</script>/`);
      expect(result).not.toContain("<");
      expect(result).toContain("&lt;");
      expect(result).toContain("&gt;");
      expect(result).toContain("&quot;");
      expect(result).toContain("&#x27;");
      expect(result).toContain("&#x2F;");
    });
  });

  describe("isValidEmail", () => {
    it.each([
      ["test@example.com", true],
      ["invalid", false],
      ["a@b", false],
    ])("isValidEmail(%s) === %s", (input, expected) => {
      expect(isValidEmail(input)).toBe(expected);
    });
  });

  describe("isValidPhone", () => {
    it.each([
      ["(555) 123-4567", true],
      ["555-123-4567", true],
      ["5551234567", true],
      ["123", false],
    ])("isValidPhone(%s) === %s", (input, expected) => {
      expect(isValidPhone(input)).toBe(expected);
    });
  });

  describe("isValidUrl", () => {
    it("returns true for valid URLs", () => {
      expect(isValidUrl("https://example.com")).toBe(true);
    });
    it("returns false for invalid URLs", () => {
      expect(isValidUrl("not-a-url")).toBe(false);
    });
  });

  describe("isSafeInteger", () => {
    it.each([
      [42, true],
      [3.14, false],
      ["42", false],
      [Number.MAX_SAFE_INTEGER + 1, false],
    ])("isSafeInteger(%s) === %s", (input, expected) => {
      expect(isSafeInteger(input)).toBe(expected);
    });
  });

  describe("isValidISODate", () => {
    it("returns true for parseable date strings", () => {
      expect(isValidISODate("2026-04-07")).toBe(true);
    });
    it("returns false for non-date strings", () => {
      expect(isValidISODate("not-a-date")).toBe(false);
    });
  });
});
