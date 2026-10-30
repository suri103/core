import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api";
import { billingApi } from "../billingApi";
import { dentalChartApi } from "../dentalChartApi";
import { treatmentPlanApi } from "../treatmentPlanApi";

vi.mock("../api", () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const mockedDelete = vi.mocked(apiClient.delete);
const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

describe("clinical and financial API services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not manufacture a healthy dental chart when loading fails", async () => {
    mockedGet.mockResolvedValue({
      success: false,
      error: { code: "UNAVAILABLE", message: "Chart service unavailable" },
    });

    await expect(dentalChartApi.getChart("patient-1")).rejects.toThrow(
      "Chart service unavailable",
    );
  });

  it("does not invent a treatment plan when creation fails", async () => {
    mockedPost.mockResolvedValue({
      success: false,
      error: { code: "REJECTED", message: "Treatment plan rejected" },
    });

    await expect(treatmentPlanApi.createPlan({} as never)).rejects.toThrow(
      "Treatment plan rejected",
    );
  });

  it("does not report a zero billing summary when loading fails", async () => {
    mockedGet.mockResolvedValue({ success: false });

    await expect(billingApi.getSummary()).rejects.toThrow(
      "Failed to load billing summary",
    );
  });

  it("does not report deletion success when the API rejects it", async () => {
    mockedDelete.mockResolvedValue({
      success: false,
      error: { code: "CONFLICT", message: "Procedure is locked" },
    });

    await expect(
      dentalChartApi.deleteProcedure("patient-1", 8, "procedure-1"),
    ).rejects.toThrow("Procedure is locked");
  });
});