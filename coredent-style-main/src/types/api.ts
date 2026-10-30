// ============================================
// CoreDent PMS - API Type Definitions
// All data, auth, and logic handled by external backend
// ============================================

// ============================================
// Authentication Types
// ============================================

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  csrf_token: string;
  must_change_password?: boolean;
}

export interface InvitationDetails {
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  practiceName: string;
  invitedBy: string;
  isValid: boolean;
}

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  practiceId: string;
  practiceName: string;
  practiceCountry: string; // The UI Switch: 'US' or 'IN'
  /** ISO 4217 currency configured on the practice (e.g. 'INR'); undefined = derive from country. */
  practiceCurrency?: string;
  mustChangePassword: boolean;
  avatarUrl?: string;
}

export type UserRole =
  | 'owner'
  | 'admin'
  | 'dentist'
  | 'hygienist'
  | 'front_desk'
  | 'group_owner'
  | 'group_admin'
  | 'accountant'
  | 'super_admin';

export interface NotificationSummary {
  unreadCount: number;
}

// ============================================
// Patient Types
// ============================================

export interface Patient {
  id: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  gender: 'male' | 'female' | 'other';
  email: string;
  phone: string;
  address: Address;
  emergencyContact: EmergencyContact;
  insuranceInfo?: InsuranceInfo;
  medicalAlerts: string[];
  status: 'active' | 'inactive';
  abhaId?: string;
  ssnLastFour?: string;
  consentRecordedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
}

export interface EmergencyContact {
  name: string;
  relationship: string;
  phone: string;
}

export interface InsuranceInfo {
  provider: string;
  policyNumber: string;
  groupNumber: string;
  subscriberName: string;
  subscriberDob: string;
}

export interface PatientListParams {
  search?: string;
  status?: 'active' | 'inactive';
  sortBy?: 'name' | 'lastVisit' | 'createdAt';
  sortOrder?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// ============================================
// Appointment Types
// ============================================

export interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  providerId: string;
  providerName: string;
  operatoryId: string;
  operatoryName: string;
  type: AppointmentType;
  status: AppointmentStatus;
  startTime: string;
  endTime: string;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export type AppointmentType = 
  | 'cleaning'
  | 'exam'
  | 'filling'
  | 'crown'
  | 'root_canal'
  | 'extraction'
  | 'whitening'
  | 'emergency'
  | 'consultation'
  | 'other';

export type AppointmentStatus = 
  | 'scheduled'
  | 'confirmed'
  | 'checked_in'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show';

export interface AppointmentListParams {
  providerId?: string;
  startDate: string;
  endDate: string;
  status?: AppointmentStatus;
}

// ============================================
// Dental Chart Types
// ============================================

export interface DentalChart {
  patientId: string;
  chartType: 'adult' | 'pediatric';
  teeth: ToothRecord[];
  lastUpdated: string;
}

export interface ToothRecord {
  toothNumber: number;
  conditions: ToothCondition[];
  procedures: ToothProcedure[];
}

export interface ToothCondition {
  id: string;
  type: ConditionType;
  surface?: ToothSurface[];
  severity?: 'mild' | 'moderate' | 'severe';
  notes?: string;
  recordedAt: string;
  recordedBy: string;
}

export type ConditionType = 
  | 'cavity'
  | 'fracture'
  | 'abscess'
  | 'periodontal'
  | 'missing'
  | 'impacted'
  | 'decay';

export type ToothSurface = 'mesial' | 'distal' | 'occlusal' | 'buccal' | 'lingual';

export interface ToothProcedure {
  id: string;
  code: string;
  name: string;
  surface?: ToothSurface[];
  status: 'existing' | 'planned' | 'completed';
  performedAt?: string;
  performedBy?: string;
  notes?: string;
}

// ============================================
// Clinical Notes Types
// ============================================

export interface ClinicalNote {
  id: string;
  patientId: string;
  appointmentId?: string;
  providerId: string;
  providerName: string;
  type: 'soap' | 'procedure' | 'general';
  subjective?: string;
  objective?: string;
  assessment?: string;
  plan?: string;
  content?: string;
  signedAt?: string;
  signedBy?: string;
  createdAt: string;
  updatedAt: string;
}

// Treatment-plan domain types live in types/treatmentPlan.ts so their names,
// statuses, dates, procedure fields, and totals match the backend adapter.

// ============================================
// Billing Types
// ============================================

export type { Invoice, InvoiceLineItem, InvoicePayment as Payment } from './billing';

// ============================================
// Reports Types
// ============================================

export interface ReportParams {
  startDate: string;
  endDate: string;
  providerId?: string;
  groupBy?: 'day' | 'week' | 'month';
}

export interface ProductionReport {
  period: string;
  production: number;
  collections: number;
  adjustments: number;
  byProvider: ProviderProduction[];
  byProcedure: ProcedureProduction[];
}

export interface ProviderProduction {
  providerId: string;
  providerName: string;
  production: number;
  collections: number;
}

export interface ProcedureProduction {
  code: string;
  name: string;
  count: number;
  production: number;
}

export interface AppointmentReport {
  period: string;
  scheduled: number;
  completed: number;
  cancelled: number;
  noShow: number;
  utilizationRate: number;
}

// ============================================
// API Response Wrapper
// ============================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, string[]>;
}
