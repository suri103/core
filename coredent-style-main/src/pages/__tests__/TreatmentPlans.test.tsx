import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TreatmentPlans from '../TreatmentPlans';
import { treatmentPlanApi } from '@/services/treatmentPlanApi';
import type { TreatmentPlan, TreatmentProcedure } from '@/types/treatmentPlan';

const { patientId, providerId } = vi.hoisted(() => ({
  patientId: '22222222-2222-4222-8222-222222222222',
  providerId: '33333333-3333-4333-8333-333333333333',
}));

vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ role: 'owner' }),
}));

vi.mock('@/services/treatmentPlanApi', () => ({
  treatmentPlanApi: {
    getPlans: vi.fn(),
    getPlan: vi.fn(),
    createPlan: vi.fn(),
    updatePlan: vi.fn(),
    deletePlan: vi.fn(),
    addProcedure: vi.fn(),
    completeProcedure: vi.fn(),
    deleteProcedure: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  patientsApi: {
    list: vi.fn().mockResolvedValue({
      success: true,
      data: { data: [{ id: patientId, firstName: 'Alice', lastName: 'Smith' }] },
    }),
  },
}));

vi.mock('@/services/schedulingApi', () => ({
  schedulingApi: {
    getProviders: vi.fn().mockResolvedValue([
      { id: providerId, name: 'Dana Rivera', role: 'dentist' },
    ]),
  },
}));

const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: mockToast }) }));

vi.mock('@/components/treatment/TreatmentPlanDialog', () => ({
  TreatmentPlanDialog: ({ open, onSubmit }: { open: boolean; onSubmit: (data: unknown) => void }) =>
    open ? (
      <button onClick={() => onSubmit({ title: 'Root Canal', patientId, providerId, patientName: 'Alice Smith', providerName: 'Dana Rivera' })}>
        Submit Create
      </button>
    ) : null,
}));

vi.mock('@/components/treatment/TreatmentPlanVisualBuilder', () => ({
  TreatmentPlanVisualBuilder: ({ plan, onUpdate }: { plan: TreatmentPlan; onUpdate: (data: unknown) => void }) => (
    <div data-testid="visual-builder">
      <span>{plan.title}</span>
      <button onClick={() => onUpdate({ title: 'Updated Plan', status: 'presented' })}>Save Update</button>
    </div>
  ),
}));

vi.mock('@/components/treatment/TreatmentPlanDetails', () => ({
  TreatmentPlanDetails: ({
    open,
    plan,
    onAddProcedure,
    onCompleteProcedure,
    onDeleteProcedure,
  }: {
    open: boolean;
    plan: TreatmentPlan | null;
    onAddProcedure: (data: unknown) => void;
    onCompleteProcedure: (id: string) => void;
    onDeleteProcedure: (id: string) => void;
  }) => open && plan ? (
    <div data-testid="plan-details">
      <button onClick={() => onAddProcedure({ procedureType: 'diagnostic', adaCode: 'D0120', description: 'Periodic exam', fee: 50 })}>Add Procedure</button>
      <button onClick={() => onCompleteProcedure('proc-1')}>Complete Procedure</button>
      <button onClick={() => onDeleteProcedure('proc-1')}>Delete Procedure</button>
    </div>
  ) : null,
}));

const procedure: TreatmentProcedure = {
  id: 'proc-1',
  treatmentPlanId: 'plan-1',
  procedureType: 'periodontal',
  adaCode: 'D4341',
  description: 'Scaling and root planing',
  status: 'planned',
  fee: 200,
  insuranceEstimate: 75,
  patientResponsibility: 125,
  isCovered: true,
  coveragePercentage: 0,
  requiresPreAuth: false,
  priority: 1,
  durationMinutes: 30,
  isAccepted: false,
  displayOrder: 0,
};

const mockPlans: TreatmentPlan[] = [
  {
    id: 'plan-1',
    title: 'Deep Cleaning',
    patientId,
    providerId,
    status: 'draft',
    totalEstimatedCost: 200,
    totalInsuranceEstimate: 75,
    totalPatientResponsibility: 125,
    procedures: [],
    phases: [],
  },
  {
    id: 'plan-2',
    title: 'Crown Work',
    patientId: '77777777-7777-4777-8777-777777777777',
    providerId,
    patientName: 'Bob Jones',
    status: 'completed',
    totalEstimatedCost: 300,
    totalInsuranceEstimate: null,
    totalPatientResponsibility: null,
    procedures: [],
    phases: [],
  },
];

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('TreatmentPlans Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(treatmentPlanApi.getPlans).mockResolvedValue(mockPlans);
    vi.mocked(treatmentPlanApi.getPlan).mockResolvedValue({ ...mockPlans[0], patientName: 'Alice Smith', providerName: 'Dana Rivera', procedures: [procedure] });
  });

  it('renders real mapped patient names, searches, and filters backend statuses', async () => {
    render(<TreatmentPlans />, { wrapper: createWrapper() });

    await screen.findByText('Deep Cleaning');
    expect(screen.getByText('Patient: Alice Smith')).toBeInTheDocument();
    expect(screen.getByText('Crown Work')).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/search plans/i), 'Alice');
    expect(screen.getByText('Deep Cleaning')).toBeInTheDocument();
    expect(screen.queryByText('Crown Work')).not.toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText(/search plans/i));
    await userEvent.click(screen.getByRole('tab', { name: /completed/i }));
    expect(screen.queryByText('Deep Cleaning')).not.toBeInTheDocument();
    expect(screen.getByText('Crown Work')).toBeInTheDocument();
  });

  it('creates draft plans with real patient and provider UUIDs', async () => {
    const newPlan = { ...mockPlans[0], id: 'plan-3', title: 'Root Canal', patientName: 'Alice Smith', providerName: 'Dana Rivera' };
    vi.mocked(treatmentPlanApi.createPlan).mockResolvedValue(newPlan);
    render(<TreatmentPlans />, { wrapper: createWrapper() });

    await userEvent.click(screen.getByRole('button', { name: /new plan/i }));
    await userEvent.click(screen.getByRole('button', { name: /submit create/i }));

    await waitFor(() => expect(treatmentPlanApi.createPlan).toHaveBeenCalledWith({
      title: 'Root Canal',
      patientId,
      providerId,
      patientName: 'Alice Smith',
      providerName: 'Dana Rivera',
      status: 'draft',
    }));
    expect(screen.getByTestId('visual-builder')).toBeInTheDocument();
  });

  it('updates using backend status names and cancels without claiming hard deletion', async () => {
    vi.mocked(treatmentPlanApi.updatePlan).mockResolvedValue({ ...mockPlans[0], title: 'Updated Plan', status: 'presented' });
    vi.mocked(treatmentPlanApi.deletePlan).mockResolvedValue(undefined);
    render(<TreatmentPlans />, { wrapper: createWrapper() });

    await screen.findByText('Deep Cleaning');
    await userEvent.click(screen.getAllByRole('button', { name: /designer/i })[0]);
    await userEvent.click(screen.getByRole('button', { name: /save update/i }));
    await waitFor(() => expect(treatmentPlanApi.updatePlan).toHaveBeenCalledWith(
      'plan-1',
      { title: 'Updated Plan', status: 'presented' },
      { patientName: 'Alice Smith', providerName: 'Dana Rivera' },
    ));

    await userEvent.click(screen.getByRole('button', { name: /cancel updated plan/i }));
    expect(screen.getByText('Cancel Treatment Plan?')).toBeInTheDocument();
    expect(screen.getByText(/remains in the clinical record/i)).toBeInTheDocument();
    const confirmButton = document.body.querySelector('button.bg-destructive');
    expect(confirmButton).not.toBeNull();
    if (!confirmButton) throw new Error('Cancel plan confirmation button not found');
    await userEvent.click(confirmButton);
    await waitFor(() => expect(treatmentPlanApi.deletePlan).toHaveBeenCalledWith('plan-1'));
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Plan cancelled' }));
  });

  it('loads details and uses actual procedure service methods', async () => {
    vi.mocked(treatmentPlanApi.addProcedure).mockResolvedValue(procedure);
    vi.mocked(treatmentPlanApi.completeProcedure).mockResolvedValue({ ...procedure, status: 'completed' });
    vi.mocked(treatmentPlanApi.deleteProcedure).mockResolvedValue(undefined);
    render(<TreatmentPlans />, { wrapper: createWrapper() });

    await screen.findByText('Deep Cleaning');
    await userEvent.click(screen.getAllByRole('button', { name: /view/i })[0]);
    await screen.findByTestId('plan-details');

    await userEvent.click(screen.getByRole('button', { name: 'Add Procedure' }));
    await waitFor(() => expect(treatmentPlanApi.addProcedure).toHaveBeenCalledWith('plan-1', {
      procedureType: 'diagnostic',
      adaCode: 'D0120',
      description: 'Periodic exam',
      fee: 50,
    }));

    await userEvent.click(screen.getByRole('button', { name: 'Complete Procedure' }));
    await waitFor(() => expect(treatmentPlanApi.completeProcedure).toHaveBeenCalledWith('proc-1'));

    await userEvent.click(screen.getByRole('button', { name: 'Delete Procedure' }));
    await waitFor(() => expect(treatmentPlanApi.deleteProcedure).toHaveBeenCalledWith('proc-1'));
  });

  it('shows an honest unavailable state when plan loading fails', async () => {
    vi.mocked(treatmentPlanApi.getPlans).mockRejectedValue(new Error('API error'));
    render(<TreatmentPlans />, { wrapper: createWrapper() });
    expect(await screen.findByText(/treatment plans unavailable/i)).toBeInTheDocument();
  });
});
