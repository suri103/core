import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';
import type {
  ProcedureStatus,
  ProcedureType,
  TreatmentPhase,
  TreatmentPlan,
  TreatmentPlanCreateInput,
  TreatmentPlanUpdateInput,
  TreatmentProcedure,
  TreatmentProcedureCreateInput,
  TreatmentStatus,
} from '@/types/treatmentPlan';

interface TreatmentPlanWire {
  id: string;
  patient_id: string;
  provider_id: string;
  plan_name: string;
  status: TreatmentStatus;
  chief_complaint?: string | null;
  diagnosis?: string | null;
  treatment_goals?: string | null;
  target_start_date?: string | null;
  target_completion_date?: string | null;
  notes?: string | null;
  total_estimated_cost?: number | string | null;
  total_insurance_estimate?: number | string | null;
  total_patient_responsibility?: number | string | null;
  created_date?: string;
  presented_date?: string | null;
  accepted_date?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface TreatmentPlanListWire {
  plans: TreatmentPlanWire[];
  count: number;
  total: number;
  next_offset?: number | null;
}

interface TreatmentPhaseWire {
  id: string;
  treatment_plan_id: string;
  phase_number: number;
  phase_name: string;
  description?: string | null;
  status: string;
  display_order: number;
}

interface TreatmentProcedureWire {
  id: string;
  treatment_plan_id: string;
  procedure_type: ProcedureType;
  ada_code: string;
  description: string;
  tooth_number?: string | null;
  surfaces?: string | null;
  quadrant?: number | null;
  fee: number | string;
  insurance_estimate: number | string;
  patient_responsibility: number | string;
  is_covered: boolean;
  coverage_percentage: number;
  requires_pre_auth: boolean;
  priority: number;
  complexity?: string | null;
  duration_minutes: number;
  status: ProcedureStatus;
  is_accepted: boolean;
  acceptance_notes?: string | null;
  display_order: number;
  phase_id?: string | null;
  appointment_id?: string | null;
  pre_auth_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface DisplayNames {
  patientName?: string;
  providerName?: string;
}

function optional<T>(value: T | null | undefined): T | undefined {
  return value ?? undefined;
}

function amount(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function adaptPhase(phase: TreatmentPhaseWire): TreatmentPhase {
  return {
    id: phase.id,
    treatmentPlanId: phase.treatment_plan_id,
    phaseNumber: phase.phase_number,
    phaseName: phase.phase_name,
    description: optional(phase.description),
    status: phase.status,
    displayOrder: phase.display_order,
  };
}

function adaptProcedure(procedure: TreatmentProcedureWire): TreatmentProcedure {
  return {
    id: procedure.id,
    treatmentPlanId: procedure.treatment_plan_id,
    procedureType: procedure.procedure_type,
    adaCode: procedure.ada_code,
    description: procedure.description,
    toothNumber: optional(procedure.tooth_number),
    surfaces: optional(procedure.surfaces),
    quadrant: optional(procedure.quadrant),
    fee: Number(procedure.fee),
    insuranceEstimate: Number(procedure.insurance_estimate),
    patientResponsibility: Number(procedure.patient_responsibility),
    isCovered: procedure.is_covered,
    coveragePercentage: procedure.coverage_percentage,
    requiresPreAuth: procedure.requires_pre_auth,
    priority: procedure.priority,
    complexity: optional(procedure.complexity),
    durationMinutes: procedure.duration_minutes,
    status: procedure.status,
    isAccepted: procedure.is_accepted,
    acceptanceNotes: optional(procedure.acceptance_notes),
    displayOrder: procedure.display_order,
    phaseId: optional(procedure.phase_id),
    appointmentId: optional(procedure.appointment_id),
    preAuthId: optional(procedure.pre_auth_id),
    createdAt: procedure.created_at,
    updatedAt: procedure.updated_at,
  };
}

function adaptPlan(
  plan: TreatmentPlanWire,
  names: DisplayNames = {},
  procedures?: TreatmentProcedure[],
  phases: TreatmentPhase[] = [],
): TreatmentPlan {
  return {
    id: plan.id,
    title: plan.plan_name,
    patientId: plan.patient_id,
    providerId: plan.provider_id,
    patientName: names.patientName,
    providerName: names.providerName,
    status: plan.status,
    chiefComplaint: optional(plan.chief_complaint),
    diagnosis: optional(plan.diagnosis),
    treatmentGoals: optional(plan.treatment_goals),
    targetStartDate: optional(plan.target_start_date),
    targetCompletionDate: optional(plan.target_completion_date),
    notes: optional(plan.notes),
    totalEstimatedCost: amount(plan.total_estimated_cost),
    totalInsuranceEstimate: amount(plan.total_insurance_estimate),
    totalPatientResponsibility: amount(plan.total_patient_responsibility),
    createdDate: plan.created_date,
    presentedDate: optional(plan.presented_date),
    acceptedDate: optional(plan.accepted_date),
    procedures: procedures ?? [],
    phases,
    proceduresLoaded: procedures !== undefined,
    createdAt: plan.created_at,
    updatedAt: plan.updated_at,
  };
}

function planCreateBody(plan: TreatmentPlanCreateInput) {
  return {
    plan_name: plan.title,
    patient_id: plan.patientId,
    provider_id: plan.providerId,
    status: plan.status ?? 'draft',
    chief_complaint: plan.chiefComplaint,
    diagnosis: plan.diagnosis,
    treatment_goals: plan.treatmentGoals,
    target_start_date: plan.targetStartDate,
    target_completion_date: plan.targetCompletionDate,
    notes: plan.notes,
  };
}

function planUpdateBody(plan: TreatmentPlanUpdateInput) {
  return {
    plan_name: plan.title,
    status: plan.status,
    chief_complaint: plan.chiefComplaint,
    diagnosis: plan.diagnosis,
    treatment_goals: plan.treatmentGoals,
    target_start_date: plan.targetStartDate,
    target_completion_date: plan.targetCompletionDate,
    notes: plan.notes,
  };
}

function procedureCreateBody(procedure: TreatmentProcedureCreateInput) {
  return {
    procedure_type: procedure.procedureType,
    ada_code: procedure.adaCode,
    description: procedure.description,
    fee: procedure.fee,
    phase_id: procedure.phaseId,
    tooth_number: procedure.toothNumber,
    surfaces: procedure.surfaces,
    quadrant: procedure.quadrant,
    insurance_estimate: procedure.insuranceEstimate,
    patient_responsibility: procedure.patientResponsibility,
    is_covered: procedure.isCovered,
    coverage_percentage: procedure.coveragePercentage,
    requires_pre_auth: procedure.requiresPreAuth,
    priority: procedure.priority,
    complexity: procedure.complexity,
    duration_minutes: procedure.durationMinutes,
    status: procedure.status,
    is_accepted: procedure.isAccepted,
    acceptance_notes: procedure.acceptanceNotes,
    display_order: procedure.displayOrder,
    appointment_id: procedure.appointmentId,
    pre_auth_id: procedure.preAuthId,
  };
}

export const treatmentPlanApi = {
  getPlans: async (): Promise<TreatmentPlan[]> => {
    const plans: TreatmentPlan[] = [];
    let offset = 0;

    // Cap pagination at 50 pages (10k plans) and require the offset to
    // advance, so a bad/poisoned next_offset cannot loop forever.
    for (let page = 0; page < 50; page++) {
      const data = requireApiData(
        await apiClient.get<TreatmentPlanListWire>('/treatment/plans/', { offset, limit: 200 }),
        'Failed to load treatment plans',
      );
      plans.push(...data.plans.map((plan) => adaptPlan(plan)));

      if (data.next_offset === null || data.next_offset === undefined) break;
      if (data.next_offset <= offset) break;
      offset = data.next_offset;
    }

    return plans;
  },

  getPlan: async (id: string, names: DisplayNames = {}): Promise<TreatmentPlan> => {
    const [planResponse, proceduresResponse, phasesResponse] = await Promise.all([
      apiClient.get<TreatmentPlanWire>(`/treatment/plans/${id}`),
      apiClient.get<{ procedures: TreatmentProcedureWire[] }>(`/treatment/plans/${id}/procedures`),
      apiClient.get<{ phases: TreatmentPhaseWire[] }>(`/treatment/plans/${id}/phases`),
    ]);
    const plan = requireApiData(planResponse, 'Failed to load treatment plan');
    const procedures = requireApiData(proceduresResponse, 'Failed to load treatment procedures');
    const phases = requireApiData(phasesResponse, 'Failed to load treatment phases');
    return adaptPlan(
      plan,
      names,
      procedures.procedures.map(adaptProcedure),
      phases.phases.map(adaptPhase),
    );
  },

  createPlan: async (plan: TreatmentPlanCreateInput): Promise<TreatmentPlan> => {
    const response = await apiClient.post<TreatmentPlanWire>('/treatment/plans/', planCreateBody(plan));
    return adaptPlan(requireApiData(response, 'Failed to create treatment plan'), plan);
  },

  updatePlan: async (
    id: string,
    plan: TreatmentPlanUpdateInput,
    names: DisplayNames = {},
  ): Promise<TreatmentPlan> => {
    const response = await apiClient.put<TreatmentPlanWire>(
      `/treatment/plans/${id}`,
      planUpdateBody(plan),
    );
    return adaptPlan(requireApiData(response, 'Failed to update treatment plan'), names);
  },

  deletePlan: async (id: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete(`/treatment/plans/${id}`),
      'Failed to cancel treatment plan',
    );
  },

  addProcedure: async (
    planId: string,
    procedure: TreatmentProcedureCreateInput,
  ): Promise<TreatmentProcedure> => {
    const response = await apiClient.post<TreatmentProcedureWire>(
      `/treatment/plans/${planId}/procedures`,
      procedureCreateBody(procedure),
    );
    return adaptProcedure(requireApiData(response, 'Failed to add treatment procedure'));
  },

  completeProcedure: async (procedureId: string): Promise<TreatmentProcedure> => {
    const response = await apiClient.put<TreatmentProcedureWire>(
      `/treatment/procedures/${procedureId}`,
      { status: 'completed' },
    );
    return adaptProcedure(requireApiData(response, 'Failed to complete treatment procedure'));
  },

  deleteProcedure: async (procedureId: string): Promise<void> => {
    requireApiSuccess(
      await apiClient.delete(`/treatment/procedures/${procedureId}`),
      'Failed to delete treatment procedure',
    );
  },
};
