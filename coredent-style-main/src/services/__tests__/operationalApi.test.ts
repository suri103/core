import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api";
import { automationApi } from "../automationApi";
import { imagingApi } from "../imagingApi";
import { insuranceApi } from "../insuranceApi";
import { patientApi } from "../patientApi";
import { schedulingApi } from "../schedulingApi";

vi.mock("../api", () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

describe("operational API services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not present a patient-service outage as an empty practice", async () => {
    mockedGet.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Patient service unavailable" },
    });

    await expect(patientApi.getPatients()).rejects.toThrow(
      "Patient service unavailable",
    );
  });

  it("does not report an appointment as cancelled when cancellation fails", async () => {
    mockedPost.mockResolvedValue({
      success: false,
      error: { code: "CONFLICT", message: "Appointment cannot be cancelled" },
    });

    await expect(
      schedulingApi.cancelAppointment("appointment-1", "Patient request"),
    ).rejects.toThrow("Appointment cannot be cancelled");
  });

  it("treats blank patient search as a valid empty query without an API call", async () => {
    await expect(schedulingApi.searchPatients("   ")).resolves.toEqual([]);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("does not report an empty claims page when insurance loading fails", async () => {
    mockedGet.mockResolvedValue({ success: false });

    await expect(insuranceApi.getClaims()).rejects.toThrow(
      "Failed to load insurance claims",
    );
  });

  it("does not present an automation outage as an empty webhook list", async () => {
    mockedGet.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Automation service unavailable" },
    });

    await expect(automationApi.getWebhooks()).rejects.toThrow(
      "Automation service unavailable",
    );
  });

  it("does not present an imaging outage as an empty image library", async () => {
    mockedGet.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Imaging service unavailable" },
    });

    await expect(imagingApi.getImages()).rejects.toThrow(
      "Imaging service unavailable",
    );
  });
});