import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PatientProfileHeader } from '../PatientProfileHeader';

const activePatient = {
  id: 'patient-1',
  firstName: 'Maya',
  lastName: 'Patel',
  dateOfBirth: '1990-02-14',
  gender: 'female',
  phone: '555-0101',
  email: 'maya@example.com',
  status: 'active',
  address: {
    street: '221B Dental Ave',
    city: 'Austin',
    state: 'TX',
    zipCode: '78701',
  },
  insuranceInfo: {
    provider: 'Delta Dental',
  },
  medicalHistory: {
    conditions: [],
    allergies: ['Penicillin'],
    medications: [],
    surgeries: [],
    familyHistory: [],
  },
  dentalHistory: {
    missingTeeth: [],
    hasImplants: false,
    hasBraces: false,
    hasPartialDenture: false,
    hasFullDenture: false,
    gumDiseaseHistory: false,
    toothSensitivity: false,
    grindsClenches: false,
  },
  notes: [],
  attachments: [],
  appointmentStats: {
    total: 0,
    completed: 0,
    cancelled: 0,
    noShow: 0,
    upcoming: 0,
  },
} as any;

const inactivePatient = {
  ...activePatient,
  status: 'inactive',
  phone: '',
  email: '',
  medicalHistory: {
    ...activePatient.medicalHistory,
    allergies: [],
  },
  address: undefined,
  insuranceInfo: undefined,
} as any;

describe('PatientProfileHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the active patient summary and triggers actions', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    const onStatusChange = vi.fn();

    render(
      <PatientProfileHeader
        patient={activePatient}
        onEdit={onEdit}
        onStatusChange={onStatusChange}
        region="US"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Maya Patel' })).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText(/medical alert/i)).toBeInTheDocument();
    expect(screen.getByText(/dob: 1990-02-14/i)).toBeInTheDocument();
    expect(screen.getByText(/insurance: delta dental/i)).toBeInTheDocument();
    expect(screen.getByText(/221b dental ave, austin/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deactivate/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /edit profile/i }));
    await user.click(screen.getByRole('button', { name: /deactivate/i }));

    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onStatusChange).toHaveBeenCalledTimes(1);
  });

  it('renders the inactive state without optional contact details', () => {
    render(
      <PatientProfileHeader
        patient={inactivePatient}
        onEdit={vi.fn()}
        onStatusChange={vi.fn()}
        region="US"
      />,
    );

    expect(screen.getByText('inactive')).toBeInTheDocument();
    expect(screen.queryByText(/medical alert/i)).not.toBeInTheDocument();
    expect(screen.getByText('No phone')).toBeInTheDocument();
    expect(screen.getByText('No email')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /activate/i })).toBeInTheDocument();
  });
});
