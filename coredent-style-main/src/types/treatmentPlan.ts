export type TreatmentStatus =
  | 'draft'
  | 'presented'
  | 'accepted'
  | 'partially_accepted'
  | 'declined'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

export type ProcedureType =
  | 'preventive'
  | 'diagnostic'
  | 'restorative'
  | 'endodontic'
  | 'periodontal'
  | 'prosthodontic'
  | 'oral_surgery'
  | 'orthodontic'
  | 'cosmetic'
  | 'other';

export type ProcedureStatus =
  | 'planned'
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

export interface TreatmentPhase {
  id: string;
  treatmentPlanId: string;
  phaseNumber: number;
  phaseName: string;
  description?: string;
  status: string;
  displayOrder: number;
}

export interface TreatmentProcedure {
  id: string;
  treatmentPlanId: string;
  procedureType: ProcedureType;
  adaCode: string;
  description: string;
  toothNumber?: string;
  surfaces?: string;
  quadrant?: number;
  fee: number;
  insuranceEstimate: number;
  patientResponsibility: number;
  isCovered: boolean;
  coveragePercentage: number;
  requiresPreAuth: boolean;
  priority: number;
  complexity?: string;
  durationMinutes: number;
  status: ProcedureStatus;
  isAccepted: boolean;
  acceptanceNotes?: string;
  displayOrder: number;
  phaseId?: string;
  appointmentId?: string;
  preAuthId?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface TreatmentPlan {
  id: string;
  title: string;
  patientId: string;
  providerId: string;
  patientName?: string;
  providerName?: string;
  status: TreatmentStatus;
  chiefComplaint?: string;
  diagnosis?: string;
  treatmentGoals?: string;
  targetStartDate?: string;
  targetCompletionDate?: string;
  notes?: string;
  totalEstimatedCost: number | null;
  totalInsuranceEstimate: number | null;
  totalPatientResponsibility: number | null;
  createdDate?: string;
  presentedDate?: string;
  acceptedDate?: string;
  procedures: TreatmentProcedure[];
  phases: TreatmentPhase[];
  proceduresLoaded?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface TreatmentPlanCreateInput {
  title: string;
  patientId: string;
  providerId: string;
  patientName?: string;
  providerName?: string;
  status?: TreatmentStatus;
  chiefComplaint?: string;
  diagnosis?: string;
  treatmentGoals?: string;
  targetStartDate?: string;
  targetCompletionDate?: string;
  notes?: string;
}

export type TreatmentPlanUpdateInput = Partial<
  Pick<
    TreatmentPlan,
    | 'title'
    | 'status'
    | 'chiefComplaint'
    | 'diagnosis'
    | 'treatmentGoals'
    | 'targetStartDate'
    | 'targetCompletionDate'
    | 'notes'
  >
>;

export interface TreatmentProcedureCreateInput {
  procedureType: ProcedureType;
  adaCode: string;
  description: string;
  fee: number;
  phaseId?: string;
  toothNumber?: string;
  surfaces?: string;
  quadrant?: number;
  insuranceEstimate?: number;
  patientResponsibility?: number;
  isCovered?: boolean;
  coveragePercentage?: number;
  requiresPreAuth?: boolean;
  priority?: number;
  complexity?: string;
  durationMinutes?: number;
  status?: ProcedureStatus;
  isAccepted?: boolean;
  acceptanceNotes?: string;
  displayOrder?: number;
  appointmentId?: string;
  preAuthId?: string;
}

export interface PlanSummary {
  totalEstimatedCost: number | null;
  totalInsuranceEstimate: number | null;
  totalPatientResponsibility: number | null;
  totalCompleted: number;
  totalPlanned: number;
}

export function calculatePlanSummary(plan: TreatmentPlan): PlanSummary {
  const totalCompleted = plan.procedures
    .filter((procedure) => procedure.status === 'completed')
    .reduce((sum, procedure) => sum + procedure.fee, 0);
  const totalPlanned = plan.procedures
    .filter((procedure) => procedure.status === 'planned')
    .reduce((sum, procedure) => sum + procedure.fee, 0);

  return {
    totalEstimatedCost: plan.totalEstimatedCost,
    totalInsuranceEstimate: plan.totalInsuranceEstimate,
    totalPatientResponsibility: plan.totalPatientResponsibility,
    totalCompleted,
    totalPlanned,
  };
}
