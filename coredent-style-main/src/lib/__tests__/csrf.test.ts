import { describe, it, expect, beforeEach } from "vitest";
import {
  getCsrfToken,
  setCsrfToken,
  clearCsrfToken,
  getCsrfHeader,
  validateCsrfToken,
  refreshCsrfToken,
  getCsrfHeaderName,
} from "../csrf";

describe("csrf", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  describe("getCsrfToken / setCsrfToken", () => {
    it("returns null when no token is set", () => {
      expect(getCsrfToken()).toBeNull();
    });

    it("returns the token after it is set", () => {
      setCsrfToken("abc123");
      expect(getCsrfToken()).toBe("abc123");
    });
  });

  describe("clearCsrfToken", () => {
    it("removes the stored token", () => {
      setCsrfToken("abc123");
      expect(getCsrfToken()).toBe("abc123");
      clearCsrfToken();
      expect(getCsrfToken()).toBeNull();
    });
  });

  describe("getCsrfHeader", () => {
    it("returns an empty object when no token is set", () => {
      expect(getCsrfHeader()).toEqual({});
    });

    it("returns the header object keyed by header name when a token exists", () => {
      setCsrfToken("abc123");
      expect(getCsrfHeader()).toEqual({ "X-CSRF-Token": "abc123" });
    });
  });

  describe("validateCsrfToken", () => {
    it("returns true when the response token matches the stored token", () => {
      setCsrfToken("abc123");
      expect(validateCsrfToken("abc123")).toBe(true);
    });

    it("returns false when the response token does not match", () => {
      setCsrfToken("abc123");
      expect(validateCsrfToken("nope")).toBe(false);
    });

    it("returns false when no token is stored", () => {
      expect(validateCsrfToken("abc123")).toBe(false);
    });
  });

  describe("refreshCsrfToken", () => {
    it("overwrites the existing token", () => {
      setCsrfToken("old");
      refreshCsrfToken("new");
      expect(getCsrfToken()).toBe("new");
    });
  });

  describe("getCsrfHeaderName", () => {
    it("returns the configured header name", () => {
      expect(getCsrfHeaderName()).toBe("X-CSRF-Token");
    });
  });
});
