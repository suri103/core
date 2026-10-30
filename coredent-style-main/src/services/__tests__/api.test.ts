import { describe, it, expect, beforeEach, vi } from "vitest";
import { apiClient, authApi, appointmentsApi } from "../api";

// Minimal Response-shaped doubles so we don't depend on Node's undici Response
// being plumbed through the jsdom environment.
const fetchResponse = (body: unknown, status = 200) => ({
  status,
  ok: status >= 200 && status < 300,
  text: async () => (status === 204 ? "" : JSON.stringify(body)),
  json: async () => body,
});

describe("API Client", () => {
  beforeEach(() => {
    apiClient.setToken(null);
    apiClient.setRefreshToken(null);
    vi.clearAllMocks();
  });

  describe("token management", () => {
    it("should set and get auth token", () => {
      apiClient.setToken("test-token");
      expect(apiClient.getToken()).toBe("test-token");
    });

    it("should clear auth token", () => {
      apiClient.setToken("test-token");
      apiClient.setToken(null);
      expect(apiClient.getToken()).toBeNull();
    });
  });

  describe("apiClient", () => {
    it("should be defined", () => {
      expect(apiClient).toBeDefined();
    });

    it("should have get method", () => {
      expect(typeof apiClient.get).toBe("function");
    });

    it("should have post method", () => {
      expect(typeof apiClient.post).toBe("function");
    });
  });

  describe("authApi", () => {
    it("should have login method", () => {
      expect(typeof authApi.login).toBe("function");
    });

    it("should have logout method", () => {
      expect(typeof authApi.logout).toBe("function");
    });

    it("should have getCurrentUser method", () => {
      expect(typeof authApi.getCurrentUser).toBe("function");
    });
  });

  describe("refreshAccessToken", () => {
    it("handles timeout AbortError during token refresh", async () => {
      const abortError = new Error("timeout");
      abortError.name = "AbortError";
      const fetchSpy = vi.spyOn(global, "fetch").mockRejectedValueOnce(abortError);

      const result = await (apiClient as any).refreshAccessToken();
      expect(result).toBeNull();
      fetchSpy.mockRestore();
    });
  });

  describe("refresh-cookie / session restoration", () => {
    it("restores a session by exchanging the refresh cookie via POST /auth/refresh", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse(
          { access_token: "rotated-access" },
          200,
        ) as unknown as Response,
      );

      const restored = await authApi.restoreSession();

      expect(restored).toBe(true);
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/auth/refresh"),
        expect.objectContaining({
          method: "POST",
          credentials: "include",
        }),
      );
      // Only the access token is visible to JavaScript; refresh is cookie-only.
      expect(apiClient.getToken()).toBe("rotated-access");
      expect(apiClient.getRefreshToken()).toBeNull();
      fetchSpy.mockRestore();
    });

    it("returns false when the refresh endpoint rejects the cookie", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse({ message: "session expired" }, 401) as unknown as Response,
      );

      const restored = await authApi.restoreSession();

      expect(restored).toBe(false);
      expect(apiClient.getToken()).toBeNull();
      fetchSpy.mockRestore();
    });
  });

  describe("401 retry on expired access token", () => {
    it("retries a 401 once with a rotated access token", async () => {
      apiClient.setToken("expired-access");
      apiClient.setRefreshToken("refresh-token");
      const fetchSpy = vi
        .spyOn(global, "fetch")
        .mockResolvedValueOnce(
          fetchResponse({ message: "expired" }, 401) as unknown as Response,
        )
        .mockResolvedValueOnce(
          fetchResponse(
            { access_token: "new-access" },
            200,
          ) as unknown as Response,
        )
        .mockResolvedValueOnce(
          fetchResponse({ id: "p-1", first_name: "Jane" }, 200) as unknown as Response,
        );

      const result = await apiClient.get<any>("/patients/p-1");

      expect(result.success).toBe(true);
      expect(result.data).toEqual({ id: "p-1", firstName: "Jane" });
      expect(apiClient.getToken()).toBe("new-access");
      expect(apiClient.getRefreshToken()).toBeNull();
      // 1) original GET 401, 2) refresh POST, 3) retried GET
      expect(fetchSpy).toHaveBeenCalledTimes(3);
      fetchSpy.mockRestore();
    });

    it("dispatches auth:logout when refresh fails after a 401", async () => {
      apiClient.setToken("expired-access");
      const logoutHandler = vi.fn();
      window.addEventListener("auth:logout", logoutHandler);

      const fetchSpy = vi
        .spyOn(global, "fetch")
        .mockResolvedValueOnce(
          fetchResponse({ message: "expired" }, 401) as unknown as Response,
        )
        .mockResolvedValueOnce(
          fetchResponse({ message: "refresh rejected" }, 401) as unknown as Response,
        );

      const result = await apiClient.get<any>("/patients/p-1");

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe("UNAUTHORIZED");
      expect(logoutHandler).toHaveBeenCalled();
      expect(apiClient.getToken()).toBeNull();

      window.removeEventListener("auth:logout", logoutHandler);
      fetchSpy.mockRestore();
    });

    it("treats a 204 from a state-changing mutation as success", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse(null, 204) as unknown as Response,
      );

      const result = await apiClient.put<void>("/staff/staff-1/deactivate", {});

      expect(result.success).toBe(true);
      expect(result.data).toBeNull();
      fetchSpy.mockRestore();
    });
  });

  describe("payload contract normalization", () => {
    it("converts snake_case responses to camelCase for normalized domains", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse(
          {
            id: "p-1",
            first_name: "Jane",
            last_visit: "2026-05-01",
          },
          200,
        ) as unknown as Response,
      );

      const result = await apiClient.get<any>("/patients/p-1");

      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        id: "p-1",
        firstName: "Jane",
        lastVisit: "2026-05-01",
      });
      fetchSpy.mockRestore();
    });

    it("groups flat patient address fields into a nested address object", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse(
          {
            id: "p-1",
            first_name: "Jane",
            address_street: "1 Main",
            address_city: "Springfield",
            address_state: "IL",
            address_zip: "62701",
          },
          200,
        ) as unknown as Response,
      );

      const result = await apiClient.get<any>("/patients/p-1");

      expect(result.data.address).toEqual({
        street: "1 Main",
        city: "Springfield",
        state: "IL",
        zipCode: "62701",
      });
      fetchSpy.mockRestore();
    });

    it("converts camelCase request bodies to snake_case for normalized domains", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockImplementationOnce(
        async (_input: RequestInfo | URL, init?: RequestInit) => {
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            first_name: "Jane",
            date_of_birth: "1990-01-01",
            emergency_contact: { name: "John", relationship: "spouse", phone: "555" },
          });
          return fetchResponse(
            { id: "p-2", first_name: "Jane", date_of_birth: "1990-01-01" },
            201,
          ) as unknown as Response;
        },
      );

      const result = await apiClient.post<any>("/patients", {
        firstName: "Jane",
        dateOfBirth: "1990-01-01",
        emergencyContact: { name: "John", relationship: "spouse", phone: "555" },
      });

      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        id: "p-2",
        firstName: "Jane",
        dateOfBirth: "1990-01-01",
      });
      fetchSpy.mockRestore();
    });

    it("leaves auth responses in their audited snake_case shape", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
        fetchResponse(
          {
            access_token: "access",
            token_type: "bearer",
            expires_in: 900,
            csrf_token: "csrf",
          },
          200,
        ) as unknown as Response,
      );

      const result = await authApi.login({
        email: "a@b.com",
        password: "p",
      });

      expect(result.success).toBe(true);
      // postValidated -> loginResponseSchema requires literal snake_case keys.
      expect(result.data).toEqual({
        access_token: "access",
        token_type: "bearer",
        expires_in: 900,
        csrf_token: "csrf",
      });
      fetchSpy.mockRestore();
    });

    it("normalizes query params to snake_case for GET requests", async () => {
      const fetchSpy = vi.spyOn(global, "fetch").mockImplementationOnce(
        async (input: RequestInfo | URL) => {
          const url = String(input);
          expect(url).toContain("patient_id=p-1");
          expect(url).not.toContain("patientId=");
          return fetchResponse({ invoices: [], count: 0 }, 200) as unknown as Response;
        },
      );

      await apiClient.get("/invoices", { patientId: "p-1", status: "paid" });
      fetchSpy.mockRestore();
    });
  });
});
describe("appointmentsApi.list", () => {
  it("unwrap the backend {appointments, count} envelope into an Appointment[]", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockImplementationOnce(
      async (input: RequestInfo | URL) => {
        const url = String(input);
        expect(url).toContain("start_date=");
        expect(url).not.toContain("startDate=");
        return fetchResponse(
          {
            appointments: [
              {
                id: "a-1",
                patient_id: "p-1",
                patient_name: "Jane Doe",
                provider_id: "d-1",
                provider_name: "Dr. Smith",
                chair_id: "c-1",
                operatory_id: "c-1",
                operatory_name: "Chair 1",
                appointment_type: "cleaning",
                type: "cleaning",
                status: "scheduled",
                start_time: "2026-08-09T09:00:00Z",
                end_time: "2026-08-09T09:30:00Z",
                duration: 30,
                notes: null,
                practice_id: "x-1",
                created_at: "2026-08-09T08:00:00Z",
                updated_at: "2026-08-09T08:00:00Z",
              },
            ],
            count: 1,
          },
          200,
        ) as unknown as Response;
      },
    );

    const result = await appointmentsApi.list({
      startDate: "2026-08-09T08:00:00Z",
      endDate: "2026-08-09T23:59:59Z",
    });

    expect(result.success).toBe(true);
    expect(Array.isArray(result.data)).toBe(true);
    expect(result.data).toHaveLength(1);
    const first = result.data?.[0] as unknown as Record<string, unknown>;
    expect(first.patientName).toBe("Jane Doe");
    expect(first.providerName).toBe("Dr. Smith");
    expect(first.operatoryId).toBe("c-1");
    expect(first.operatoryName).toBe("Chair 1");
    expect(first.type).toBe("cleaning");
    expect(first.appointmentType).toBe("cleaning");
    expect(first.startTime).toBe("2026-08-09T09:00:00Z");
    fetchSpy.mockRestore();
  });
});
