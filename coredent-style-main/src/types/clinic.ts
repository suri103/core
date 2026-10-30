// ============================================
// CoreDent PMS - Clinic Settings Types
// Types for practice/clinic configuration
// ============================================

export interface ClinicSettings {
  id: string;
  name: string;
  logoUrl?: string;
  email: string;
  phone: string;
  fax?: string;
  website?: string;
  address: ClinicAddress;
  workingHours: WorkingHours;
  chairs: Chair[];
  appointmentTypes: AppointmentTypeConfig[];
  timezone: string;
  dateFormat: 'MM/DD/YYYY' | 'DD/MM/YYYY' | 'YYYY-MM-DD';
  currency: string;
  /** Retention override in years (docs/DATA_RETENTION_POLICY.md § 6).
   *  null = platform default (7y). Purging never shortens below the floor. */
  retentionYears?: number | null;
  /** Jurisdiction code for the retention preset picker (e.g. 'CA', 'USA'). */
  jurisdiction?: string | null;
  /** Age of majority used for minor-retention (default 18). */
  majorityAge?: number | null;
  /** Extra years past majority a minor record is kept (default 7). */
  minorRetentionYears?: number | null;
  updatedAt: string;
}

export interface ClinicAddress {
  street: string;
  suite?: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
}

export interface WorkingHours {
  monday: DaySchedule;
  tuesday: DaySchedule;
  wednesday: DaySchedule;
  thursday: DaySchedule;
  friday: DaySchedule;
  saturday: DaySchedule;
  sunday: DaySchedule;
}

export interface DaySchedule {
  isOpen: boolean;
  openTime: string; // HH:MM format
  closeTime: string; // HH:MM format
  breakStart?: string;
  breakEnd?: string;
}

export interface Chair {
  id: string;
  name: string;
  description?: string;
  isActive: boolean;
  color: string;
}

export interface AppointmentTypeConfig {
  id: string;
  name: string;
  code: string;
  duration: number; // in minutes
  color: string;
  isActive: boolean;
  allowOnlineBooking: boolean;
  description?: string;
}

// Default values for new clinics
export const defaultWorkingHours: WorkingHours = {
  monday: { isOpen: true, openTime: '08:00', closeTime: '17:00' },
  tuesday: { isOpen: true, openTime: '08:00', closeTime: '17:00' },
  wednesday: { isOpen: true, openTime: '08:00', closeTime: '17:00' },
  thursday: { isOpen: true, openTime: '08:00', closeTime: '17:00' },
  friday: { isOpen: true, openTime: '08:00', closeTime: '17:00' },
  saturday: { isOpen: false, openTime: '09:00', closeTime: '14:00' },
  sunday: { isOpen: false, openTime: '09:00', closeTime: '14:00' },
};

export const defaultAppointmentTypes: AppointmentTypeConfig[] = [
  { id: '1', name: 'New Patient Exam', code: 'D0150', duration: 60, color: '#3B82F6', isActive: true, allowOnlineBooking: true },
  { id: '2', name: 'Periodic Exam', code: 'D0120', duration: 30, color: '#10B981', isActive: true, allowOnlineBooking: true },
  { id: '3', name: 'Cleaning (Prophylaxis)', code: 'D1110', duration: 45, color: '#8B5CF6', isActive: true, allowOnlineBooking: true },
  { id: '4', name: 'Filling', code: 'D2391', duration: 45, color: '#F59E0B', isActive: true, allowOnlineBooking: false },
  { id: '5', name: 'Crown Prep', code: 'D2740', duration: 90, color: '#EF4444', isActive: true, allowOnlineBooking: false },
  { id: '6', name: 'Root Canal', code: 'D3310', duration: 90, color: '#EC4899', isActive: true, allowOnlineBooking: false },
  { id: '7', name: 'Emergency', code: 'D0140', duration: 30, color: '#DC2626', isActive: true, allowOnlineBooking: false },
  { id: '8', name: 'Consultation', code: 'D9310', duration: 30, color: '#6366F1', isActive: true, allowOnlineBooking: true },
];

export const defaultChairs: Chair[] = [
  { id: '1', name: 'Operatory 1', description: 'Main treatment room', isActive: true, color: '#3B82F6' },
  { id: '2', name: 'Operatory 2', description: 'Secondary treatment room', isActive: true, color: '#10B981' },
  { id: '3', name: 'Hygiene Room', description: 'Cleaning and preventive care', isActive: true, color: '#8B5CF6' },
];

// US States for address dropdown
export const US_STATES = [
  { code: 'AL', name: 'Alabama' }, { code: 'AK', name: 'Alaska' }, { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' }, { code: 'CA', name: 'California' }, { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' }, { code: 'DE', name: 'Delaware' }, { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' }, { code: 'HI', name: 'Hawaii' }, { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' }, { code: 'IN', name: 'Indiana' }, { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' }, { code: 'KY', name: 'Kentucky' }, { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' }, { code: 'MD', name: 'Maryland' }, { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' }, { code: 'MN', name: 'Minnesota' }, { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' }, { code: 'MT', name: 'Montana' }, { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' }, { code: 'NH', name: 'New Hampshire' }, { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' }, { code: 'NY', name: 'New York' }, { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' }, { code: 'OH', name: 'Ohio' }, { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' }, { code: 'PA', name: 'Pennsylvania' }, { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' }, { code: 'SD', name: 'South Dakota' }, { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' }, { code: 'UT', name: 'Utah' }, { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' }, { code: 'WA', name: 'Washington' }, { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' }, { code: 'WY', name: 'Wyoming' },
];
