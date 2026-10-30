import { apiClient } from "./api";
import { requireApiData, requireApiSuccess } from "./apiResponse";
import type {
  DentalChart,
  ProcedureStatus,
  ToothCondition,
  ToothProcedure,
} from "@/types/dentalChart";

export const dentalChartApi = {
  getChart: async (patientId: string): Promise<DentalChart> =>
    requireApiData(
      await apiClient.get<DentalChart>(`/patients/${patientId}/chart`),
      "Failed to load dental chart",
    ),

  updateToothCondition: async (
    patientId: string,
    toothNumber: number,
    condition: ToothCondition,
  ): Promise<DentalChart> =>
    requireApiData(
      await apiClient.put<DentalChart>(
        `/patients/${patientId}/chart/teeth/${toothNumber}/condition`,
        { condition },
      ),
      "Failed to update tooth condition",
    ),

  addProcedure: async (
    patientId: string,
    toothNumber: number,
    procedure: Omit<ToothProcedure, "id">,
  ): Promise<ToothProcedure> =>
    requireApiData(
      await apiClient.post<ToothProcedure>(
        `/patients/${patientId}/chart/teeth/${toothNumber}/procedures`,
        procedure,
      ),
      "Failed to add dental procedure",
    ),

  updateProcedureStatus: async (
    patientId: string,
    toothNumber: number,
    procedureId: string,
    status: ProcedureStatus,
  ): Promise<void> => {
    requireApiSuccess(
      await apiClient.put<void>(
        `/patients/${patientId}/chart/teeth/${toothNumber}/procedures/${procedureId}/status`,
        { status },
      ),
      "Failed to update dental procedure status",
    );
  },

  deleteProcedure: async (
    patientId: string,
    toothNumber: number,
    procedureId: string,
  ): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete<void>(
        `/patients/${patientId}/chart/teeth/${toothNumber}/procedures/${procedureId}`,
      ),
      "Failed to delete dental procedure",
    );
  },
};