import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PatientMedicalTab } from '../PatientMedicalTab';
import type { MedicalHistory, DentalHistory } from '@/types/patient';

const populatedMedicalHistory: MedicalHistory = {
  conditions: ['Hypertension'],
  allergies: ['Penicillin'],
  medications: ['Lisinopril'],
  surgeries: ['Root canal'],
  familyHistory: ['Diabetes'],
  bloodType: 'O+',
  primaryPhysician: 'Dr. Lee',
  physicianPhone: '555-9999',
};

const populatedDentalHistory: DentalHistory = {
  lastCleaning: '2026-05-20',
  lastXrays: '2026-05-18',
  missingTeeth: [14, 15],
  hasImplants: true,
  hasBraces: false,
  hasPartialDenture: false,
  hasFullDenture: false,
  gumDiseaseHistory: true,
  toothSensitivity: true,
  grindsClenches: true,
  previousDentist: 'Smile Care',
  reasonForLeaving: 'Moved city',
};

const emptyMedicalHistory: MedicalHistory = {
  conditions: [],
  allergies: [],
  medications: [],
  surgeries: [],
  familyHistory: [],
};

const emptyDentalHistory: DentalHistory = {
  missingTeeth: [],
  hasImplants: false,
  hasBraces: false,
  hasPartialDenture: false,
  hasFullDenture: false,
  gumDiseaseHistory: false,
  toothSensitivity: false,
  grindsClenches: false,
};

describe('PatientMedicalTab', () => {
  it('renders populated medical and dental history details', () => {
    render(
      <PatientMedicalTab
        medicalHistory={populatedMedicalHistory}
        dentalHistory={populatedDentalHistory}
      />,
    );

    expect(screen.getByText('Medical Conditions')).toBeInTheDocument();
    expect(screen.getByText('Hypertension')).toBeInTheDocument();
    expect(screen.getByText('Penicillin')).toBeInTheDocument();
    expect(screen.getByText('Lisinopril')).toBeInTheDocument();
    expect(screen.getByText('Root canal')).toBeInTheDocument();
    expect(screen.getByText('Diabetes')).toBeInTheDocument();
    expect(screen.getByText('Dental History')).toBeInTheDocument();
    expect(screen.getByText('May 20, 2026')).toBeInTheDocument();
    expect(screen.getByText('May 18, 2026')).toBeInTheDocument();
    expect(screen.getByText('Gum Disease History')).toBeInTheDocument();
    expect(screen.getByText('Tooth Sensitivity')).toBeInTheDocument();
    expect(screen.getByText('Grinds/Clenches')).toBeInTheDocument();
    expect(screen.getByText('Has Implants')).toBeInTheDocument();
    expect(screen.getByText('Missing Teeth: 14, 15')).toBeInTheDocument();
    expect(screen.getByText('Dr. Lee')).toBeInTheDocument();
    expect(screen.getByText('555-9999')).toBeInTheDocument();
    expect(screen.getByText('O+')).toBeInTheDocument();
  });

  it('renders empty-state placeholders for medical history', () => {
    render(
      <PatientMedicalTab
        medicalHistory={emptyMedicalHistory}
        dentalHistory={emptyDentalHistory}
      />,
    );

    expect(screen.getByText('None reported')).toBeInTheDocument();
    expect(screen.getByText('No known allergies')).toBeInTheDocument();
    expect(screen.getByText('No medications')).toBeInTheDocument();
    expect(screen.getAllByText('Unknown').length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText('Not Specified').length).toBeGreaterThanOrEqual(2);
  });
});
