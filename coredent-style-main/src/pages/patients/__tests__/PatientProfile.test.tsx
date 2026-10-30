import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate, useParams } from 'react-router-dom';
import PatientProfile from '../PatientProfile';
import { useAuth } from '@/contexts/auth-context';
import { patientsApi } from '@/services/api';

const toastMock = vi.hoisted(() => vi.fn());

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/services/api', () => ({
  patientsApi: {
    getById: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('@/services/patientApi', () => ({
  patientApi: {
    getAppointmentHistory: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('@/components/patients/AppointmentHistory', () => ({
  AppointmentHistory: () => <div data-testid="appointment-history">Appointment History</div>,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(),
    useNavigate: vi.fn(),
  };
});

const mockUseAuth = vi.mocked(useAuth);
const mockPatientsApi = vi.mocked(patientsApi);
const mockUseParams = vi.mocked(useParams);
const mockUseNavigate = vi.mocked(useNavigate);

const navigate = vi.fn();

const patient = {
  id: 'patient-1',
  firstName: 'Maya',
  lastName: 'Patel',
  dateOfBirth: '1990-02-14',
  gender: 'female' as const,
  phone: '555-0101',
  email: 'maya@example.com',
  status: 'active' as const,
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
    conditions: ['Hypertension'],
    allergies: ['Penicillin'],
    medications: ['Lisinopril'],
    surgeries: ['Root canal'],
    familyHistory: ['Diabetes'],
    bloodType: 'O+',
    lastPhysicalExam: '2026-05-01',
    primaryPhysician: 'Dr. Lee',
    physicianPhone: '555-9999',
  },
  dentalHistory: {
    lastCleaning: '2026-05-20',
    lastXrays: '2026-05-18',
    missingTeeth: [14],
    hasImplants: false,
    hasBraces: false,
    hasPartialDenture: false,
    hasFullDenture: false,
    gumDiseaseHistory: true,
    toothSensitivity: true,
    grindsClenches: false,
    previousDentist: 'Smile Care',
    reasonForLeaving: 'Moved city',
  },
  notes: [
    {
      id: 'note-1',
      type: 'clinical' as const,
      content: 'Routine follow-up completed.',
      createdAt: '2026-06-01',
      createdBy: 'dr-1',
      createdByName: 'Dr. Singh',
      isAlert: true,
      isPinned: false,
    },
  ],
  attachments: [
    {
      id: 'att-1',
      name: 'insurance-card.pdf',
      type: 'application/pdf',
      size: 1536,
      url: 'https://example.com/insurance-card.pdf',
      category: 'insurance' as const,
      uploadedAt: '2026-06-10',
      uploadedBy: 'staff-1',
      uploadedByName: 'Front Desk',
    },
  ],
  appointmentStats: {
    total: 12,
    completed: 10,
    cancelled: 1,
    noShow: 1,
    upcoming: 2,
    lastVisit: '2026-06-01',
    nextAppointment: '2026-07-01',
  },
};

function arrangePatientProfile({
  id = 'patient-1',
  data = { success: true, data: patient },
}: {
  id?: string | null;
  data?: unknown;
} = {}) {
  mockUseParams.mockReturnValue({ id } as never);
  mockUseNavigate.mockReturnValue(navigate as never);
  mockUseAuth.mockReturnValue({
    user: { practiceCountry: 'US' },
  } as never);
  mockPatientsApi.getById.mockResolvedValue(data as never);
  mockPatientsApi.update.mockResolvedValue({ success: true, data: patient } as never);
}

describe('PatientProfile page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the patient record and supports core actions', async () => {
    arrangePatientProfile();
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PatientProfile />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Maya Patel' })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: /patients/i })).toBeInTheDocument();
    expect(screen.getByText(/medical alert: allergies/i)).toBeInTheDocument();
    expect(screen.getByText(/routine follow-up completed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /schedule appointment/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByText(/total visits/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /deactivate/i }));
    await waitFor(() => expect(mockPatientsApi.update).toHaveBeenCalledWith('patient-1', { status: 'inactive' }));

    await user.click(screen.getByRole('tab', { name: /medical\/dental/i }));
    expect(screen.getByText(/primary care physician/i)).toBeInTheDocument();
    expect(screen.getByText(/hypertension/i)).toBeInTheDocument();
    expect(screen.getAllByText(/penicillin/i)[0]).toBeInTheDocument();
    expect(screen.getByText(/root canal/i)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /files & images/i }));
    expect(screen.getByText('insurance-card.pdf')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /appointments/i }));
    expect(screen.getByTestId("appointment-history")).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /schedule appointment/i }));
    // The patient's NAME must not travel in the URL: query strings persist in
    // history, leak through Referer and are logged by every intermediary. Only
    // the opaque id is passed (and Schedule reads nothing else).
    expect(navigate).toHaveBeenCalledWith('/schedule?patientId=patient-1');
    expect(navigate).not.toHaveBeenCalledWith(
      expect.stringContaining('patientName'),
    );
  });

  it('shows the error state when the patient cannot be loaded', async () => {
    arrangePatientProfile({
      id: 'patient-2',
      data: { success: false, error: { message: 'Failed to load patient profile' } },
    });

    render(
      <MemoryRouter>
        <PatientProfile />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to load patient profile');
  });

  it('navigates to /patients if no id is provided in URL', async () => {
    arrangePatientProfile({ id: null });
    render(
      <MemoryRouter>
        <PatientProfile />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith('/patients');
    });
  });
});
