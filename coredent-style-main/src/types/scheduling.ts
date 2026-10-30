import type { AppointmentStatus } from './api';

export interface ScheduleAppointment {
  id: string;
  patientId: string;
  patientName: string;
  patientEmail?: string;
  patientPhone?: string;
  providerId: string;
  providerName: string;
  chairId: string;
  chairName?: string;
  type: string;
  status: AppointmentStatus;
  startTime: Date;
  endTime: Date;
  duration: number; // in minutes
  notes?: string;
}

export interface AppointmentFormData {
  patientId: string;
  patientName: string;
  providerId: string;
  chairId: string;
  type: string;
  date: Date;
  startTime: string; // e.g. "09:30" or "09:30 AM"
  duration: number; // in minutes
  notes?: string;
}

export interface PatientSearchResult {
  id: string;
  name: string;
  phone: string;
  email?: string;
}

export interface ScheduleProvider {
  id: string;
  name: string;
  role?: string;
  color?: string;
}

export function parseTimeString(time: string): { hours: number; minutes: number } {
  if (!time) return { hours: 0, minutes: 0 };
  const cleanTime = time.trim();
  const ampmMatch = cleanTime.match(/^(1[0-2]|0?[1-9]):([0-5][0-9])\s*(AM|PM)$/i);
  if (ampmMatch) {
    let hours = parseInt(ampmMatch[1], 10);
    const minutes = parseInt(ampmMatch[2], 10);
    const ampm = ampmMatch[3].toUpperCase();
    if (ampm === 'PM' && hours < 12) hours += 12;
    if (ampm === 'AM' && hours === 12) hours = 0;
    return { hours, minutes };
  }
  
  const parts = cleanTime.split(':');
  const hours = parseInt(parts[0], 10) || 0;
  const minutes = parseInt(parts[1], 10) || 0;
  return { hours, minutes };
}
