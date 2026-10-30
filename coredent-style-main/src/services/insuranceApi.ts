import type {
  ClaimStatus,
  CreateCarrierInput,
  CreateClaimInput,
  CreatePatientInsuranceInput,
  CreatePreAuthorizationInput,
  InsuranceCarrier,
  InsuranceClaim,
  InsurancePage,
  InsurancePreAuthorization,
  PatientInsurance,
  PreAuthStatus,
  ProcedureCode,
  UpdateCarrierInput,
  UpdateClaimInput,
  UpdatePatientInsuranceInput,
  UpdatePreAuthorizationInput,
} from '@/types/insurance';
import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';

type DecimalWire = string | number;
type Nullable<T> = T | null;

interface CarrierWire {
  id: string;
  name: string;
  phone: Nullable<string>;
  fax: Nullable<string>;
  email: Nullable<string>;
  website: Nullable<string>;
  address_line1: Nullable<string>;
  address_line2: Nullable<string>;
  city: Nullable<string>;
  state: Nullable<string>;
  zip_code: Nullable<string>;
  payer_id: Nullable<string>;
  edi_enabled: boolean;
  notes: Nullable<string>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface PatientInsuranceWire {
  id: string;
  patient_id: string;
  carrier_id: string;
  subscriber_id: string;
  group_number: Nullable<string>;
  relationship_to_subscriber: PatientInsurance['relationshipToSubscriber'];
  is_primary: boolean;
  is_active: boolean;
  coverage_type: Nullable<string>;
  annual_maximum: Nullable<DecimalWire>;
  annual_deductible: Nullable<DecimalWire>;
  deductible_met: DecimalWire;
  benefits_used: DecimalWire;
  preventive_coverage: number;
  basic_coverage: number;
  major_coverage: number;
  ortho_coverage: number;
  effective_date: Nullable<string>;
  expiration_date: Nullable<string>;
  verified: boolean;
  verified_at: Nullable<string>;
  verified_by: Nullable<string>;
  created_at: string;
  updated_at: string;
}

interface ProcedureCodeWire {
  code: string;
  description: string;
  fee: DecimalWire;
}

interface ClaimWire {
  id: string;
  practice_id: string;
  patient_id: string;
  patient_insurance_id: string;
  carrier_id: string;
  claim_number: string;
  status: ClaimStatus;
  service_date: string;
  submission_date: Nullable<string>;
  received_date: Nullable<string>;
  paid_date: Nullable<string>;
  billed_amount: DecimalWire;
  allowed_amount: Nullable<DecimalWire>;
  deductible_amount: DecimalWire;
  copay_amount: DecimalWire;
  paid_amount: DecimalWire;
  patient_responsibility: DecimalWire;
  procedure_codes: ProcedureCodeWire[];
  diagnosis_codes: string[];
  notes: Nullable<string>;
  denial_reason: Nullable<string>;
  edi_transaction_id: Nullable<string>;
  edi_batch_id: Nullable<string>;
  confirmation_number: Nullable<string>;
  outstanding_balance: DecimalWire;
  created_at: string;
  updated_at: string;
}

interface PreAuthorizationWire {
  id: string;
  patient_id: string;
  patient_insurance_id: string;
  authorization_number: string;
  status: PreAuthStatus;
  request_date: string;
  procedure_codes: ProcedureCodeWire[] | string;
  estimated_cost: DecimalWire;
  approval_date: Nullable<string>;
  expiration_date: Nullable<string>;
  approved_amount: Nullable<DecimalWire>;
  notes: Nullable<string>;
  created_at: string;
  updated_at: string;
}

interface ClaimListWire {
  claims: ClaimWire[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
}

interface PreAuthorizationListWire {
  pre_authorizations: PreAuthorizationWire[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
}

function decimalToNumber(value: DecimalWire, field: string): number {
  const numberValue = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numberValue)) {
    throw new Error(`Invalid decimal value for ${field}`);
  }
  return numberValue;
}

function optionalDecimalToNumber(value: Nullable<DecimalWire>, field: string): number | undefined {
  return value === null ? undefined : decimalToNumber(value, field);
}

function optional<T>(value: Nullable<T>): T | undefined {
  return value === null ? undefined : value;
}

function mapProcedureCode(wire: ProcedureCodeWire): ProcedureCode {
  return {
    code: wire.code,
    description: wire.description,
    fee: decimalToNumber(wire.fee, 'procedure_codes.fee'),
  };
}

function parseProcedureCodes(value: ProcedureCodeWire[] | string): ProcedureCodeWire[] {
  if (Array.isArray(value)) return value;
  const parsed: unknown = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error('Invalid procedure_codes response');
  }
  return parsed as ProcedureCodeWire[];
}

function mapCarrier(wire: CarrierWire): InsuranceCarrier {
  return {
    id: wire.id,
    name: wire.name,
    phone: optional(wire.phone),
    fax: optional(wire.fax),
    email: optional(wire.email),
    website: optional(wire.website),
    addressLine1: optional(wire.address_line1),
    addressLine2: optional(wire.address_line2),
    city: optional(wire.city),
    state: optional(wire.state),
    zipCode: optional(wire.zip_code),
    payerId: optional(wire.payer_id),
    ediEnabled: wire.edi_enabled,
    notes: optional(wire.notes),
    isActive: wire.is_active,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  };
}

function mapPatientInsurance(wire: PatientInsuranceWire): PatientInsurance {
  return {
    id: wire.id,
    patientId: wire.patient_id,
    carrierId: wire.carrier_id,
    subscriberId: wire.subscriber_id,
    groupNumber: optional(wire.group_number),
    relationshipToSubscriber: wire.relationship_to_subscriber,
    isPrimary: wire.is_primary,
    isActive: wire.is_active,
    coverageType: optional(wire.coverage_type),
    annualMaximum: optionalDecimalToNumber(wire.annual_maximum, 'annual_maximum'),
    annualDeductible: optionalDecimalToNumber(wire.annual_deductible, 'annual_deductible'),
    deductibleMet: decimalToNumber(wire.deductible_met, 'deductible_met'),
    benefitsUsed: decimalToNumber(wire.benefits_used, 'benefits_used'),
    preventiveCoverage: wire.preventive_coverage,
    basicCoverage: wire.basic_coverage,
    majorCoverage: wire.major_coverage,
    orthoCoverage: wire.ortho_coverage,
    effectiveDate: optional(wire.effective_date),
    expirationDate: optional(wire.expiration_date),
    verified: wire.verified,
    verifiedAt: optional(wire.verified_at),
    verifiedBy: optional(wire.verified_by),
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  };
}

function mapClaim(wire: ClaimWire): InsuranceClaim {
  return {
    id: wire.id,
    practiceId: wire.practice_id,
    patientId: wire.patient_id,
    patientInsuranceId: wire.patient_insurance_id,
    carrierId: wire.carrier_id,
    claimNumber: wire.claim_number,
    status: wire.status,
    serviceDate: wire.service_date,
    submissionDate: optional(wire.submission_date),
    receivedDate: optional(wire.received_date),
    paidDate: optional(wire.paid_date),
    billedAmount: decimalToNumber(wire.billed_amount, 'billed_amount'),
    allowedAmount: optionalDecimalToNumber(wire.allowed_amount, 'allowed_amount'),
    deductibleAmount: decimalToNumber(wire.deductible_amount, 'deductible_amount'),
    copayAmount: decimalToNumber(wire.copay_amount, 'copay_amount'),
    paidAmount: decimalToNumber(wire.paid_amount, 'paid_amount'),
    patientResponsibility: decimalToNumber(wire.patient_responsibility, 'patient_responsibility'),
    procedureCodes: wire.procedure_codes.map(mapProcedureCode),
    diagnosisCodes: wire.diagnosis_codes,
    notes: optional(wire.notes),
    denialReason: optional(wire.denial_reason),
    ediTransactionId: optional(wire.edi_transaction_id),
    ediBatchId: optional(wire.edi_batch_id),
    confirmationNumber: optional(wire.confirmation_number),
    outstandingBalance: decimalToNumber(wire.outstanding_balance, 'outstanding_balance'),
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  };
}

function mapPreAuthorization(wire: PreAuthorizationWire): InsurancePreAuthorization {
  return {
    id: wire.id,
    patientId: wire.patient_id,
    patientInsuranceId: wire.patient_insurance_id,
    authorizationNumber: wire.authorization_number,
    status: wire.status,
    requestDate: wire.request_date,
    procedureCodes: parseProcedureCodes(wire.procedure_codes).map(mapProcedureCode),
    estimatedCost: decimalToNumber(wire.estimated_cost, 'estimated_cost'),
    approvalDate: optional(wire.approval_date),
    expirationDate: optional(wire.expiration_date),
    approvedAmount: optionalDecimalToNumber(wire.approved_amount, 'approved_amount'),
    notes: optional(wire.notes),
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  };
}

function carrierPayload(data: CreateCarrierInput | UpdateCarrierInput) {
  return {
    name: data.name,
    phone: data.phone,
    fax: data.fax,
    email: data.email,
    website: data.website,
    address_line1: data.addressLine1,
    address_line2: data.addressLine2,
    city: data.city,
    state: data.state,
    zip_code: data.zipCode,
    payer_id: data.payerId,
    edi_enabled: data.ediEnabled,
    notes: data.notes,
    is_active: data.isActive,
  };
}

function patientInsurancePayload(data: CreatePatientInsuranceInput | UpdatePatientInsuranceInput) {
  return {
    carrier_id: data.carrierId,
    subscriber_id: data.subscriberId,
    group_number: data.groupNumber,
    relationship_to_subscriber: data.relationshipToSubscriber,
    is_primary: data.isPrimary,
    is_active: data.isActive,
    coverage_type: data.coverageType,
    annual_maximum: data.annualMaximum,
    annual_deductible: data.annualDeductible,
    deductible_met: data.deductibleMet,
    benefits_used: data.benefitsUsed,
    preventive_coverage: data.preventiveCoverage,
    basic_coverage: data.basicCoverage,
    major_coverage: data.majorCoverage,
    ortho_coverage: data.orthoCoverage,
    effective_date: data.effectiveDate,
    expiration_date: data.expirationDate,
  };
}

function procedurePayload(procedure: ProcedureCode) {
  return {
    code: procedure.code,
    description: procedure.description,
    fee: procedure.fee,
  };
}

export const insuranceApi = {
  async getCarriers(filters?: { search?: string; isActive?: boolean }): Promise<InsuranceCarrier[]> {
    const wire = requireApiData(
      await apiClient.get<{ carriers: CarrierWire[]; count: number }>('/insurance/carriers/', {
        search: filters?.search,
        is_active: filters?.isActive,
      }),
      'Failed to load insurance carriers',
    );
    return wire.carriers.map(mapCarrier);
  },

  async getCarrier(carrierId: string): Promise<InsuranceCarrier> {
    return mapCarrier(requireApiData(
      await apiClient.get<CarrierWire>(`/insurance/carriers/${carrierId}`),
      'Failed to load insurance carrier',
    ));
  },

  async createCarrier(data: CreateCarrierInput): Promise<InsuranceCarrier> {
    return mapCarrier(requireApiData(
      await apiClient.post<CarrierWire>('/insurance/carriers/', carrierPayload(data)),
      'Failed to create carrier',
    ));
  },

  async updateCarrier(carrierId: string, data: UpdateCarrierInput): Promise<InsuranceCarrier> {
    return mapCarrier(requireApiData(
      await apiClient.put<CarrierWire>(`/insurance/carriers/${carrierId}`, carrierPayload(data)),
      'Failed to update carrier',
    ));
  },

  async getPatientInsurance(patientId: string): Promise<PatientInsurance[]> {
    const wire = requireApiData(
      await apiClient.get<{ insurances: PatientInsuranceWire[]; count: number }>(`/insurance/patients/${patientId}/policies`),
      'Failed to load patient insurance',
    );
    return wire.insurances.map(mapPatientInsurance);
  },

  async addPatientInsurance(patientId: string, data: CreatePatientInsuranceInput): Promise<PatientInsurance> {
    return mapPatientInsurance(requireApiData(
      await apiClient.post<PatientInsuranceWire>(`/insurance/patients/${patientId}/policies`, patientInsurancePayload(data)),
      'Failed to add insurance',
    ));
  },

  async updateInsurancePolicy(policyId: string, data: UpdatePatientInsuranceInput): Promise<PatientInsurance> {
    return mapPatientInsurance(requireApiData(
      await apiClient.put<PatientInsuranceWire>(`/insurance/policies/${policyId}`, patientInsurancePayload(data)),
      'Failed to update insurance',
    ));
  },

  async deleteInsurancePolicy(policyId: string): Promise<void> {
    requireApiSuccess(
      await apiClient.delete(`/insurance/policies/${policyId}`),
      'Failed to delete insurance policy',
    );
  },

  async getClaims(filters?: {
    patientId?: string;
    status?: ClaimStatus;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  }): Promise<InsurancePage<InsuranceClaim>> {
    const wire = requireApiData(
      await apiClient.get<ClaimListWire>('/insurance/claims/', {
        patient_id: filters?.patientId,
        status: filters?.status,
        start_date: filters?.startDate,
        end_date: filters?.endDate,
        limit: filters?.limit,
        offset: filters?.offset,
      }),
      'Failed to load insurance claims',
    );
    return {
      items: wire.claims.map(mapClaim),
      count: wire.count,
      total: wire.total,
      limit: wire.limit,
      offset: wire.offset,
      nextOffset: wire.next_offset,
    };
  },

  async createClaim(data: CreateClaimInput): Promise<InsuranceClaim> {
    return mapClaim(requireApiData(
      await apiClient.post<ClaimWire>('/insurance/claims/', {
        patient_insurance_id: data.patientInsuranceId,
        service_date: data.serviceDate,
        billed_amount: data.billedAmount,
        procedure_codes: data.procedureCodes.map(procedurePayload),
        diagnosis_codes: data.diagnosisCodes,
        notes: data.notes,
      }),
      'Failed to create claim',
    ));
  },

  async updateClaim(claimId: string, data: UpdateClaimInput): Promise<InsuranceClaim> {
    return mapClaim(requireApiData(
      await apiClient.put<ClaimWire>(`/insurance/claims/${claimId}`, {
        status: data.status,
        submission_date: data.submissionDate,
        received_date: data.receivedDate,
        paid_date: data.paidDate,
        allowed_amount: data.allowedAmount,
        deductible_amount: data.deductibleAmount,
        copay_amount: data.copayAmount,
        paid_amount: data.paidAmount,
        patient_responsibility: data.patientResponsibility,
        notes: data.notes,
        denial_reason: data.denialReason,
      }),
      'Failed to update claim',
    ));
  },

  async submitClaim(claimId: string): Promise<InsuranceClaim> {
    return mapClaim(requireApiData(
      await apiClient.post<ClaimWire>(`/insurance/claims/${claimId}/submit`, {}),
      'Failed to submit claim',
    ));
  },

  async getPreAuthorizations(filters?: {
    patientId?: string;
    status?: PreAuthStatus;
    limit?: number;
    offset?: number;
  }): Promise<InsurancePage<InsurancePreAuthorization>> {
    const wire = requireApiData(
      await apiClient.get<PreAuthorizationListWire>('/insurance/pre-auth/', {
        patient_id: filters?.patientId,
        status: filters?.status,
        limit: filters?.limit,
        offset: filters?.offset,
      }),
      'Failed to load insurance pre-authorizations',
    );
    return {
      items: wire.pre_authorizations.map(mapPreAuthorization),
      count: wire.count,
      total: wire.total,
      limit: wire.limit,
      offset: wire.offset,
      nextOffset: wire.next_offset,
    };
  },

  async createPreAuthorization(data: CreatePreAuthorizationInput): Promise<InsurancePreAuthorization> {
    return mapPreAuthorization(requireApiData(
      await apiClient.post<PreAuthorizationWire>('/insurance/pre-auth/', {
        patient_insurance_id: data.patientInsuranceId,
        request_date: data.requestDate,
        procedure_codes: data.procedureCodes.map(procedurePayload),
        estimated_cost: data.estimatedCost,
        notes: data.notes,
      }),
      'Failed to create pre-authorization',
    ));
  },

  async updatePreAuthorization(preAuthId: string, data: UpdatePreAuthorizationInput): Promise<InsurancePreAuthorization> {
    return mapPreAuthorization(requireApiData(
      await apiClient.put<PreAuthorizationWire>(`/insurance/pre-auth/${preAuthId}`, {
        status: data.status,
        approval_date: data.approvalDate,
        expiration_date: data.expirationDate,
        approved_amount: data.approvedAmount,
        notes: data.notes,
      }),
      'Failed to update pre-authorization',
    ));
  },

  // ============================================
  // Live Clearinghouse (EDI 837D / 835 ERA)
  // ============================================

  async export837DClaim(claimId: string): Promise<string> {
    const res = await apiClient.get<string>(`/edi/claims/${claimId}/export-837d`);
    return typeof res === 'string' ? res : ((res as any)?.data || (res as any) || '');
  },

  async reconcileEraText(eraText: string): Promise<any> {
    const res = await apiClient.post<any>('/edi/era/reconcile-text', { era_text: eraText });
    return (res as any)?.data || (res as any);
  },

  async uploadEraFile(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post<any>('/edi/era/upload', formData);
    return (res as any)?.data || (res as any);
  },
};
