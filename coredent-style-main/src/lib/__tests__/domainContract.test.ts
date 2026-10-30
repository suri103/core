import { describe, it, expect } from "vitest";
import {
  shouldNormalizeContract,
  normalizeRequestPayload,
  normalizeResponsePayload,
} from "../domainContract";

describe("domainContract", () => {
  describe("shouldNormalizeContract", () => {
    it("normalizes the core data domains", () => {
      expect(shouldNormalizeContract("/patients")).toBe(true);
      expect(shouldNormalizeContract("/patients/p-1")).toBe(true);
      expect(shouldNormalizeContract("/appointments")).toBe(true);
      expect(shouldNormalizeContract("/notes/abc")).toBe(true);
      // Live billing routes (verified vs api.py): /billing/*. /treatment/*
      // is intentionally excluded — treatmentPlanApi.ts owns a typed
      // snake_case adapter, and a global camelCase pass double-converted
      // those payloads into undefined fields. Dead prefixes /invoices,
      // /payments, /treatment-plans, /dental-chart never matched a real
      // route and must not normalize.
      expect(shouldNormalizeContract("/billing/invoices")).toBe(true);
      expect(shouldNormalizeContract("/billing/payments")).toBe(true);
      expect(shouldNormalizeContract("/treatment/plans")).toBe(false);
      expect(shouldNormalizeContract("/treatment/plans/p-1")).toBe(false);
      expect(shouldNormalizeContract("/invoices")).toBe(false);
      expect(shouldNormalizeContract("/payments")).toBe(false);
      expect(shouldNormalizeContract("/treatment-plans")).toBe(false);
      expect(shouldNormalizeContract("/dental-chart")).toBe(false);
      expect(shouldNormalizeContract("/staff")).toBe(true);
      expect(shouldNormalizeContract("/staff/invitations")).toBe(true);
      // /communications was listed as exempt on the claim that its frontend
      // already spoke snake_case. It did not: the page and the service types are
      // camelCase, so creates 422'd, updates silently wrote nothing, and the
      // conversations list crashed reading `patientId`.
      expect(shouldNormalizeContract("/communications/conversations")).toBe(true);
      expect(shouldNormalizeContract("/communications/templates")).toBe(true);
    });

    it("normalizes list endpoints even when they carry a query string", () => {
      // The GET helpers append query params before the predicate sees the URL.
      expect(shouldNormalizeContract("/patients?page=2&limit=10")).toBe(true);
      expect(shouldNormalizeContract("/billing/invoices?status=paid&patient_id=p1")).toBe(true);
      expect(shouldNormalizeContract("/appointments?from=2026-01-01#top")).toBe(true);
    });

    it("does not normalize audited snake_case contracts", () => {
      expect(shouldNormalizeContract("/auth/login")).toBe(false);
      expect(shouldNormalizeContract("/auth/me")).toBe(false);
      expect(shouldNormalizeContract("/booking/public/abc")).toBe(false);
      expect(shouldNormalizeContract("/portal/logout")).toBe(false);
      expect(shouldNormalizeContract("/insurance/claims")).toBe(false);
    });
  });

  describe("normalizeRequestPayload", () => {
    it("converts camelCase bodies to snake_case for normalized domains", () => {
      const body = {
        firstName: "Jane",
        dateOfBirth: "1990-01-01",
        emergencyContact: { name: "John", relationship: "spouse", phone: "555" },
      };
      expect(normalizeRequestPayload("/patients", body)).toEqual({
        first_name: "Jane",
        date_of_birth: "1990-01-01",
        emergency_contact: { name: "John", relationship: "spouse", phone: "555" },
      });
    });

    it("flattens the nested patient address for the backend", () => {
      const body = {
        firstName: "Jane",
        address: { street: "1 Main", city: "Springfield", state: "IL", zipCode: "62701" },
      };
      expect(normalizeRequestPayload("/patients", body)).toEqual({
        first_name: "Jane",
        address_street: "1 Main",
        address_city: "Springfield",
        address_state: "IL",
        address_zip: "62701",
      });
    });

    it("leaves FormData untouched", () => {
      const formData = new FormData();
      formData.append("file", "x");
      expect(normalizeRequestPayload("/patients/p-1/attachments", formData)).toBe(formData);
    });
  });

  describe("normalizeResponsePayload", () => {
    it("converts snake_case responses to camelCase", () => {
      const response = {
        patient_id: "p-1",
        first_name: "Jane",
        last_visit: "2026-05-01",
      };
      expect(normalizeResponsePayload("/patients/p-1", response)).toEqual({
        patientId: "p-1",
        firstName: "Jane",
        lastVisit: "2026-05-01",
      });
    });

    it("groups flat address_* fields into a nested address object", () => {
      const response = {
        id: "p-1",
        first_name: "Jane",
        address_street: "1 Main",
        address_city: "Springfield",
        address_state: "IL",
        address_zip: "62701",
      };
      expect(normalizeResponsePayload("/patients/p-1", response)).toEqual({
        id: "p-1",
        firstName: "Jane",
        address: {
          street: "1 Main",
          city: "Springfield",
          state: "IL",
          zipCode: "62701",
        },
      });
    });

    it("normalizes items inside legacy data paginated patient responses", () => {
      const response = {
        data: [
          { id: "p-1", first_name: "John", address_zip: "62701" },
        ],
        total: 1,
        page: 1,
        limit: 10,
        total_pages: 1,
      };
      const result = normalizeResponsePayload("/patients", response) as unknown as {
        data: Array<{ id: string; firstName: string; address: { zipCode: string } }>;
        totalPages: number;
      };
      expect(result.data[0].firstName).toBe("John");
      expect(result.data[0].address.zipCode).toBe("62701");
      expect(result.totalPages).toBe(1);
    });

    it("adapts the backend items/pages patient page to the frontend contract", () => {
      const response = {
        success: true,
        items: [
          { id: "p-1", first_name: "John", address_zip: "62701" },
        ],
        total: 1,
        page: 1,
        limit: 10,
        pages: 1,
      };
      const result = normalizeResponsePayload("/patients", response) as unknown as {
        data: Array<{ id: string; firstName: string; address: { zipCode: string } }>;
        total: number;
        page: number;
        limit: number;
        totalPages: number;
      };
      expect(result.data[0].firstName).toBe("John");
      expect(result.data[0].address.zipCode).toBe("62701");
      expect(result.total).toBe(1);
      expect(result.page).toBe(1);
      expect(result.limit).toBe(10);
      expect(result.totalPages).toBe(1);
    });

    it("leaves already-camelCase payloads intact", () => {
      const response = { patientId: "p-1", firstName: "Jane" };
      expect(normalizeResponsePayload("/patients/p-1", response)).toEqual(response);
    });
  });
});