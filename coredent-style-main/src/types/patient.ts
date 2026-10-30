// ============================================
// CoreDent PMS - Patient Types
// Extended types for patient management module
// ============================================

import type { Patient, Address, EmergencyContact, InsuranceInfo } from './api';

// Extended patient type with additional fields
export interface PatientRecord extends Patient {
  // Medical history
  medicalHistory: MedicalHistory;
  // Dental history
  dentalHistory: DentalHistory;
  // Notes timeline
  notes: PatientNote[];
  // Attached files
  attachments: PatientAttachment[];
  // Appointment count summary
  appointmentStats: AppointmentStats;
}

export interface MedicalHistory {
  conditions: string[];
  allergies: string[];
  medications: string[];
  surgeries: string[];
  familyHistory: string[];
  bloodType?: string;
  lastPhysicalExam?: string;
  primaryPhysician?: string;
  physicianPhone?: string;
}

export interface DentalHistory {
  lastCleaning?: string;
  lastXrays?: string;
  missingTeeth: number[];
  hasImplants: boolean;
  hasBraces: boolean;
  hasPartialDenture: boolean;
  hasFullDenture: boolean;
  gumDiseaseHistory: boolean;
  toothSensitivity: boolean;
  grindsClenches: boolean;
  previousDentist?: string;
  reasonForLeaving?: string;
}

export interface PatientNote {
  id: string;
  type: 'general' | 'clinical' | 'billing' | 'communication' | 'alert';
  content: string;
  createdAt: string;
  createdBy: string;
  createdByName: string;
  isAlert: boolean;
  isPinned: boolean;
}

export interface PatientAttachment {
  id: string;
  name: string;
  type: string; // MIME type
  size: number; // bytes
  url: string;
  category: 'insurance' | 'xray' | 'consent' | 'referral' | 'other';
  uploadedAt: string;
  uploadedBy: string;
  uploadedByName: string;
}

export interface AppointmentStats {
  total: number;
  completed: number;
  cancelled: number;
  noShow: number;
  upcoming: number;
  lastVisit?: string;
  nextAppointment?: string;
}

// Form data for creating/editing patients
export interface PatientFormData {
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
  medicalHistory: MedicalHistory;
  dentalHistory: DentalHistory;
}

// Search and filter params
export interface PatientSearchParams {
  query?: string;
  status?: 'active' | 'inactive' | 'all';
  hasUpcoming?: boolean;
  hasMedicalAlert?: boolean;
  sortBy?: 'name' | 'lastVisit' | 'createdAt' | 'nextAppointment';
  sortOrder?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

// Patient list item (lighter version for list view)
export interface PatientListItem {
  id: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  phone: string;
  email: string;
  status: 'active' | 'inactive';
  hasMedicalAlerts: boolean;
  medicalAlerts: string[];
  lastVisit?: string;
  nextAppointment?: string;
  balance?: number;
}

// Quick action types
export type PatientQuickAction = 
  | 'schedule'
  | 'call'
  | 'email'
  | 'addNote'
  | 'viewChart'
  | 'createInvoice';

// Note type colors
export const noteTypeConfig: Record<PatientNote['type'], { label: string; color: string; bgClass: string }> = {
  general: { label: 'General', color: '#6B7280', bgClass: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200' },
  clinical: { label: 'Clinical', color: '#3B82F6', bgClass: 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-200' },
  billing: { label: 'Billing', color: '#10B981', bgClass: 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200' },
  communication: { label: 'Communication', color: '#8B5CF6', bgClass: 'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-200' },
  alert: { label: 'Alert', color: '#EF4444', bgClass: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200' },
};

// Attachment category config
export const attachmentCategoryConfig: Record<PatientAttachment['category'], { label: string; icon: string }> = {
  insurance: { label: 'Insurance', icon: 'FileText' },
  xray: { label: 'X-Ray', icon: 'Image' },
  consent: { label: 'Consent Form', icon: 'FileCheck' },
  referral: { label: 'Referral', icon: 'Send' },
  other: { label: 'Other', icon: 'File' },
};

// Default empty medical history
export const defaultMedicalHistory: MedicalHistory = {
  conditions: [],
  allergies: [],
  medications: [],
  surgeries: [],
  familyHistory: [],
};

// Default empty dental history
export const defaultDentalHistory: DentalHistory = {
  missingTeeth: [],
  hasImplants: false,
  hasBraces: false,
  hasPartialDenture: false,
  hasFullDenture: false,
  gumDiseaseHistory: false,
  toothSensitivity: false,
  grindsClenches: false,
};
