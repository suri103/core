export type ClaimStatus =
  | 'draft'
  | 'pending'
  | 'submitting'
  | 'submitted'
  | 'in_review'
  | 'approved'
  | 'partially_approved'
  | 'denied'
  | 'paid'
  | 'appealed'
  | 'submission_failed';

export type ClaimUpdateStatus = Exclude<
  ClaimStatus,
  'draft' | 'submitting' | 'submission_failed'
>;

export type PreAuthStatus = 'pending' | 'approved' | 'denied';

export type RelationshipToSubscriber = 'self' | 'spouse' | 'child' | 'other';

export interface InsuranceCarrier {
  id: string;
  name: string;
  phone?: string;
  fax?: string;
  email?: string;
  website?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  zipCode?: string;
  payerId?: string;
  ediEnabled: boolean;
  notes?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface PatientInsurance {
  id: string;
  patientId: string;
  carrierId: string;
  subscriberId: string;
  groupNumber?: string;
  relationshipToSubscriber: RelationshipToSubscriber;
  isPrimary: boolean;
  isActive: boolean;
  coverageType?: string;
  annualMaximum?: number;
  annualDeductible?: number;
  deductibleMet: number;
  benefitsUsed: number;
  preventiveCoverage: number;
  basicCoverage: number;
  majorCoverage: number;
  orthoCoverage: number;
  effectiveDate?: string;
  expirationDate?: string;
  verified: boolean;
  verifiedAt?: string;
  verifiedBy?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProcedureCode {
  code: string;
  description: string;
  fee: number;
}

export interface InsuranceClaim {
  id: string;
  practiceId: string;
  patientId: string;
  patientInsuranceId: string;
  carrierId: string;
  claimNumber: string;
  status: ClaimStatus;
  serviceDate: string;
  submissionDate?: string;
  receivedDate?: string;
  paidDate?: string;
  billedAmount: number;
  allowedAmount?: number;
  deductibleAmount: number;
  copayAmount: number;
  paidAmount: number;
  patientResponsibility: number;
  procedureCodes: ProcedureCode[];
  diagnosisCodes: string[];
  notes?: string;
  denialReason?: string;
  ediTransactionId?: string;
  ediBatchId?: string;
  confirmationNumber?: string;
  outstandingBalance: number;
  createdAt: string;
  updatedAt: string;
}

export interface InsurancePreAuthorization {
  id: string;
  patientId: string;
  patientInsuranceId: string;
  authorizationNumber: string;
  status: PreAuthStatus;
  requestDate: string;
  procedureCodes: ProcedureCode[];
  estimatedCost: number;
  approvalDate?: string;
  expirationDate?: string;
  approvedAmount?: number;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface InsurancePage<T> {
  items: T[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  nextOffset: number | null;
}

export interface CreateCarrierInput {
  name: string;
  phone?: string;
  fax?: string;
  email?: string;
  website?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  zipCode?: string;
  payerId?: string;
  ediEnabled?: boolean;
  notes?: string;
  isActive?: boolean;
}

export type UpdateCarrierInput = Partial<CreateCarrierInput>;

export interface CreatePatientInsuranceInput {
  carrierId: string;
  subscriberId: string;
  groupNumber?: string;
  relationshipToSubscriber?: RelationshipToSubscriber;
  isPrimary?: boolean;
  isActive?: boolean;
  coverageType?: string;
  annualMaximum?: number;
  annualDeductible?: number;
  deductibleMet?: number;
  benefitsUsed?: number;
  preventiveCoverage?: number;
  basicCoverage?: number;
  majorCoverage?: number;
  orthoCoverage?: number;
  effectiveDate?: string;
  expirationDate?: string;
}

export type UpdatePatientInsuranceInput = Partial<CreatePatientInsuranceInput>;

export interface CreateClaimInput {
  patientInsuranceId: string;
  serviceDate: string;
  billedAmount: number;
  procedureCodes: ProcedureCode[];
  diagnosisCodes?: string[];
  notes?: string;
}

export interface UpdateClaimInput {
  status?: ClaimUpdateStatus;
  submissionDate?: string;
  receivedDate?: string;
  paidDate?: string;
  allowedAmount?: number;
  deductibleAmount?: number;
  copayAmount?: number;
  paidAmount?: number;
  patientResponsibility?: number;
  notes?: string;
  denialReason?: string;
}

export interface CreatePreAuthorizationInput {
  patientInsuranceId: string;
  requestDate: string;
  procedureCodes: ProcedureCode[];
  estimatedCost: number;
  notes?: string;
}

export interface UpdatePreAuthorizationInput {
  status?: PreAuthStatus;
  approvalDate?: string;
  expirationDate?: string;
  approvedAmount?: number;
  notes?: string;
}
