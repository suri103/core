import { describe, it, expect } from "vitest";
import {
  sanitizeHtml,
  sanitizeText,
  sanitizeUrl,
  sanitizePatientNote,
  sanitizeJson,
  sanitizeEmail,
  sanitizePhone,
  createSanitizedHtml,
} from "../sanitize";

describe("sanitize", () => {
  describe("sanitizeHtml", () => {
    it("allows the configured safe tags", () => {
      const result = sanitizeHtml("<b>bold</b> <i>italic</i>");
      expect(result).toContain("<b>bold</b>");
      expect(result).toContain("<i>italic</i>");
    });

    it("strips script tags", () => {
      const result = sanitizeHtml('<b>ok</b><script>alert(1)</script>');
      expect(result).not.toContain("<script");
      expect(result).toContain("<b>ok</b>");
    });

    it("strips disallowed tags like iframe", () => {
      const result = sanitizeHtml("<p>hi</p><iframe src='x'></iframe>");
      expect(result).not.toContain("<iframe");
      expect(result).toContain("<p>hi</p>");
    });
  });

  describe("sanitizeText", () => {
    it("escapes HTML entities in raw text", () => {
      expect(sanitizeText("<script>alert('x')</script>")).not.toContain("<script>");
    });

    it("preserves plain text", () => {
      expect(sanitizeText("hello world")).toBe("hello world");
    });
  });

  describe("sanitizeUrl", () => {
    it("allows http and https URLs", () => {
      expect(sanitizeUrl("https://example.com")).toBe("https://example.com/");
      expect(sanitizeUrl("http://example.com")).toBe("http://example.com/");
    });

    it("allows mailto and tel protocols", () => {
      expect(sanitizeUrl("mailto:test@example.com")).toBe("mailto:test@example.com");
      expect(sanitizeUrl("tel:+15551234567")).toBe("tel:+15551234567");
    });

    it("allows relative URLs starting with / or #", () => {
      expect(sanitizeUrl("/patients")).toBe("/patients");
      expect(sanitizeUrl("#section")).toBe("#section");
    });

    it("returns empty string for empty input", () => {
      expect(sanitizeUrl("")).toBe("");
    });

    it("rejects javascript protocol URLs", () => {
      expect(sanitizeUrl("javascript:alert(1)")).toBe("");
    });
  });

  describe("sanitizePatientNote", () => {
    it("allows headings and basic formatting", () => {
      const result = sanitizePatientNote("<h2>Title</h2><p>Body</p>");
      expect(result).toContain("<h2>Title</h2>");
      expect(result).toContain("<p>Body</p>");
    });

    it("strips attributes like href", () => {
      const result = sanitizePatientNote('<a href="https://x.com">link</a>');
      expect(result).not.toContain('href=');
    });
  });

  describe("sanitizeJson", () => {
    it("sanitizes string values", () => {
      const result = sanitizeJson({ name: "<b>x</b>", count: 3 });
      expect(result.count).toBe(3);
      expect(result.name).not.toContain("<b>");
    });

    it("recurses into nested objects", () => {
      const result = sanitizeJson({ nested: { value: "<script>" } });
      expect((result.nested as { value: string }).value).not.toContain("<script>");
    });

    it("preserves non-string, non-object values and arrays", () => {
      const arr = [1, 2];
      const result = sanitizeJson({ flag: true, list: arr, num: 42 });
      expect(result.flag).toBe(true);
      expect(result.list).toBe(arr);
      expect(result.num).toBe(42);
    });
  });

  describe("sanitizeEmail", () => {
    it("returns the lowercased trimmed email when valid", () => {
      expect(sanitizeEmail("  Test@Example.COM ")).toBe("test@example.com");
    });

    it("returns null for an invalid email", () => {
      expect(sanitizeEmail("not-an-email")).toBeNull();
    });
  });

  describe("sanitizePhone", () => {
    it("removes non-numeric characters except +", () => {
      expect(sanitizePhone("(555) 123-4567")).toBe("5551234567");
      expect(sanitizePhone("+1 (555) 123-4567")).toBe("+15551234567");
    });
  });

  describe("createSanitizedHtml", () => {
    it("returns a dangerouslySetInnerHTML object", () => {
      const result = createSanitizedHtml("<b>hi</b>");
      expect(result).toHaveProperty("__html");
      expect(result.__html).toContain("<b>hi</b>");
    });
  });
});
