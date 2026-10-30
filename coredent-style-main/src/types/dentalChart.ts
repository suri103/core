export type ToothCondition = 'sound' | 'decay' | 'filled' | 'missing' | 'crown';
export type ProcedureStatus = 'planned' | 'completed';
export type ToothSurface = 'O' | 'M' | 'D' | 'F' | 'L' | 'I' | 'B' | 'G';

export interface ToothProcedure {
  id: string;
  code: string;
  description: string;
  surface?: string;
  cost: number;
  status: ProcedureStatus;
  date: string;
  notes?: string;
}

export interface ToothData {
  number: number;
  name: string;
  condition: ToothCondition;
  surfaces?: ToothSurface[];
  procedures?: ToothProcedure[];
}

export interface DentalChart {
  id: string;
  patientId: string;
  patientName?: string;
  teeth: ToothData[];
  updatedAt: string;
  lastUpdated?: string;
}
