import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  comms: {} as any,
  createTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  createReminder: vi.fn(),
  updateReminder: vi.fn(),
  deleteReminder: vi.fn(),
  selectConversation: vi.fn(),
  sendConversationMessage: vi.fn(),
  treatmentPlanApi: {
    getPlans: vi.fn(),
    createPlan: vi.fn(),
    updatePlan: vi.fn(),
    deletePlan: vi.fn(),
    addProcedure: vi.fn(),
    completeProcedure: vi.fn(),
    getPlan: vi.fn(),
    deleteProcedure: vi.fn(),
  },
  triggerAutomation: vi.fn(),
  patientsApi: {
    getById: vi.fn(),
    list: vi.fn(),
  },
  clinicalNotesApi: {
    listByPatient: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  createSubscription: vi.fn(),
  cancelSubscription: vi.fn(),
  subscriptionsState: {
    plans: [] as any[],
    subscriptions: [] as any[],
    stats: null as Record<string, number> | null,
    plansLoading: false,
    subsLoading: false,
  },
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ user: { id: 'provider-1', firstName: 'Dr', lastName: 'Curie' }, role: 'owner' }),
}));

vi.mock('@/hooks/useCommunications', () => ({
  useCommunications: () => mocks.comms,
}));

vi.mock('@/services/treatmentPlanApi', () => ({
  treatmentPlanApi: mocks.treatmentPlanApi,
}));

vi.mock('@/services/automationApi', () => ({
  triggerAutomation: mocks.triggerAutomation,
}));

vi.mock('@/services/api', () => ({
  patientsApi: mocks.patientsApi,
  clinicalNotesApi: mocks.clinicalNotesApi,
}));

vi.mock('@/hooks/useSubscriptions', () => ({
  useSubscriptionPlans: () => ({ data: mocks.subscriptionsState.plans, isLoading: mocks.subscriptionsState.plansLoading }),
  useSubscriptions: () => ({ data: mocks.subscriptionsState.subscriptions, isLoading: mocks.subscriptionsState.subsLoading }),
  useSubscriptionStats: () => ({ data: mocks.subscriptionsState.stats }),
  useCreateSubscription: () => ({ mutateAsync: mocks.createSubscription }),
  useCancelSubscription: () => ({ mutateAsync: mocks.cancelSubscription }),
}));

vi.mock('@/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }: any) => <div>{children}</div>,
  AlertDialogTrigger: ({ children }: any) => <>{children}</>,
  AlertDialogContent: ({ children }: any) => <div role="dialog">{children}</div>,
  AlertDialogHeader: ({ children }: any) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: any) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: any) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }: any) => <p>{children}</p>,
  AlertDialogCancel: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
  AlertDialogAction: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
}));
vi.mock('@/components/treatment/TreatmentPlanCard', () => ({
  TreatmentPlanCard: ({ plan, onView, onEdit, onDelete }: any) => (
    <article>
      <h2>{plan.title}</h2>
      <button onClick={() => onView(plan)}>View {plan.title}</button>
      <button onClick={() => onEdit(plan)}>Edit {plan.title}</button>
      <button onClick={() => onDelete(plan)}>Delete {plan.title}</button>
    </article>
  ),
}));

vi.mock('@/components/treatment/TreatmentPlanDialog', () => ({
  TreatmentPlanDialog: ({ open, onSubmit }: any) => open ? (
    <div role="dialog" aria-label="plan-dialog">
      <button onClick={() => onSubmit({
        title: 'Implant Plan',
        patientId: 'patient-1',
        patientName: 'Ada Lovelace',
        description: 'Implant treatment',
      })}>
        Submit New Plan
      </button>
    </div>
  ) : null,
}));

vi.mock('@/components/treatment/TreatmentPlanDetails', () => ({
  TreatmentPlanDetails: ({ open, plan, onAddProcedure, onCompleteProcedure, onDeleteProcedure }: any) => open && plan ? (
    <section>
      <h2>Details for {plan.title}</h2>
      <button onClick={() => onAddProcedure({ procedureCode: 'D1110', procedureName: 'Cleaning', phase: 'phase_1', estimatedCost: 125 })}>Add Procedure</button>
      <button onClick={() => onCompleteProcedure('procedure-1')}>Complete Procedure</button>
      <button onClick={() => onDeleteProcedure('procedure-1')}>Delete Procedure</button>
    </section>
  ) : null,
}));

vi.mock('@/components/treatment/TreatmentPlanVisualBuilder', () => ({
  TreatmentPlanVisualBuilder: ({ plan, onUpdate, onCancel }: any) => (
    <section>
      <h2>Visual Builder for {plan.title}</h2>
      <button onClick={async () => {
        await onUpdate({ ...plan, status: 'accepted', title: `${plan.title} Updated` });
        onCancel();
      }}>Save Visual Builder</button>
      <button onClick={onCancel}>Cancel Builder</button>
    </section>
  ),
}));

import ClinicalNotes from '../ClinicalNotes';
import Communications from '../Communications';
import Subscriptions from '../Subscriptions';
import TreatmentPlans from '../TreatmentPlans';

function renderWithProviders(ui: React.ReactElement, initialEntry = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const plan = {
  id: 'plan-1',
  title: 'Crown Plan',
  patientId: 'patient-1',
  providerId: 'provider-1',
  patientName: 'Ada Lovelace',
  status: 'presented',
  totalEstimatedCost: 900,
  totalInsuranceEstimate: 0,
  totalPatientResponsibility: 900,
  phases: [],
  procedures: [{
    id: 'procedure-1',
    treatmentPlanId: 'plan-1',
    procedureType: 'restorative',
    adaCode: 'D2740',
    description: 'Crown',
    fee: 900,
    insuranceEstimate: 0,
    patientResponsibility: 900,
    isCovered: false,
    coveragePercentage: 0,
    requiresPreAuth: false,
    priority: 1,
    durationMinutes: 90,
    status: 'planned',
    isAccepted: false,
    displayOrder: 1,
  }],
  createdAt: '2026-06-01T00:00:00Z',
  updatedAt: '2026-06-01T00:00:00Z',
};

const patient = {
  id: 'patient-1',
  firstName: 'Ada',
  lastName: 'Lovelace',
  email: 'ada@example.com',
};

const note = {
  id: 'note-1',
  patientId: 'patient-1',
  providerId: 'provider-1',
  providerName: 'Dr Curie',
  type: 'general',
  content: 'Existing clinical note',
  createdAt: '2026-06-01T12:00:00Z',
  updatedAt: '2026-06-01T12:00:00Z',
};

describe('high-impact core page workflows', () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();

    mocks.createTemplate.mockResolvedValue({ id: 'template-new' });
    mocks.updateTemplate.mockResolvedValue({ id: 'template-1' });
    mocks.deleteTemplate.mockResolvedValue(true);
    mocks.createReminder.mockResolvedValue({ id: 'reminder-new' });
    mocks.updateReminder.mockResolvedValue({ id: 'reminder-1' });
    mocks.deleteReminder.mockResolvedValue(true);
    mocks.selectConversation.mockResolvedValue(undefined);
    mocks.sendConversationMessage.mockResolvedValue({ id: 'message-new' });
    mocks.comms = {
      templates: [{ id: 'template-1', name: 'Appointment Reminder', messageType: 'sms', content: 'See you soon', category: 'appointment', variables: ['patient_name'], isActive: true, isDefault: false }],
      templatesLoading: false,
      fetchTemplates: vi.fn().mockResolvedValue(undefined),
      createTemplate: mocks.createTemplate,
      updateTemplate: mocks.updateTemplate,
      deleteTemplate: mocks.deleteTemplate,
      reminders: [{ id: 'reminder-1', name: 'One day reminder', reminderType: 'appointment', daysBefore: 1, hoursBefore: 0, minutesBefore: 0, messageType: 'sms', isActive: true, sendOnWeekends: false, maxReminders: 2, templateId: 'template-1' }],
      remindersLoading: false,
      fetchReminders: vi.fn().mockResolvedValue(undefined),
      createReminder: mocks.createReminder,
      updateReminder: mocks.updateReminder,
      deleteReminder: mocks.deleteReminder,
      conversations: [{ id: 'conversation-1', patientId: 'patient-abcdef', channel: 'sms', lastMessagePreview: 'Please confirm', lastMessageAt: '2026-06-01T12:00:00Z', unreadCount: 2 }],
      conversationsLoading: false,
      fetchConversations: vi.fn().mockResolvedValue(undefined),
      selectConversation: mocks.selectConversation,
      conversationMessages: [{ id: 'message-1', conversationId: 'conversation-1', senderType: 'patient', content: 'Please confirm', createdAt: '2026-06-01T12:00:00Z' }],
      sendConversationMessage: mocks.sendConversationMessage,
      summary: { unreadMessages: 2, messages: { totalSent: 5, deliveryRate: 98 }, reminders: { pending: 3 } },
      summaryLoading: false,
      fetchSummary: vi.fn().mockResolvedValue(undefined),
      error: null,
    };

    mocks.treatmentPlanApi.getPlans.mockResolvedValue([plan]);
    mocks.treatmentPlanApi.createPlan.mockResolvedValue({ ...plan, id: 'plan-2', title: 'Implant Plan', procedures: [] });
    mocks.treatmentPlanApi.updatePlan.mockResolvedValue({ ...plan, status: 'accepted', title: 'Crown Plan Updated' });
    mocks.treatmentPlanApi.deletePlan.mockResolvedValue(undefined);
    mocks.treatmentPlanApi.addProcedure.mockResolvedValue({ id: 'procedure-2', procedureName: 'Cleaning', estimatedCost: 125, status: 'planned' });
    mocks.treatmentPlanApi.completeProcedure.mockResolvedValue(undefined);
    mocks.treatmentPlanApi.getPlan
      .mockResolvedValueOnce({ ...plan })
      .mockResolvedValueOnce({ ...plan })
      .mockResolvedValueOnce({ ...plan, procedures: [{ ...plan.procedures[0], status: 'completed' }] })
      .mockResolvedValueOnce({ ...plan, procedures: [] });
    mocks.treatmentPlanApi.deleteProcedure.mockResolvedValue(undefined);

    mocks.patientsApi.getById.mockResolvedValue({ success: true, data: patient });
    mocks.patientsApi.list.mockResolvedValue({ success: true, data: { data: [patient] } });
    mocks.clinicalNotesApi.listByPatient.mockResolvedValue({ success: true, data: [note] });
    mocks.clinicalNotesApi.create.mockResolvedValue({ success: true, data: { ...note, id: 'note-2', content: 'New note content' } });
    mocks.clinicalNotesApi.update.mockImplementation(async (id: string, payload: any) => ({ success: true, data: { ...note, ...payload, id } }));
    mocks.clinicalNotesApi.delete.mockResolvedValue({ success: true });

    mocks.subscriptionsState.plans = [{ id: 'plan-basic', name: 'Basic', description: 'Starter', short_description: 'Starter', amount: '99', interval: 'monthly', trial_period_days: 14, features: ['Scheduling'], is_active: true }];
    mocks.subscriptionsState.subscriptions = [{ id: 'sub-1', plan_id: 'plan-pro', status: 'active', current_period_end: '2026-07-01T00:00:00Z', next_billing_date: '2026-07-01T00:00:00Z', cancel_at_period_end: false }];
    mocks.subscriptionsState.stats = { total_active: 3, total_trials: 1, mrr: 299, mrr_growth_percent: 12, total_past_due: 0, churn_rate: 2, total_canceled_this_month: 0 };
    mocks.subscriptionsState.plansLoading = false;
    mocks.subscriptionsState.subsLoading = false;
    mocks.createSubscription.mockResolvedValue({ id: 'sub-new' });
    mocks.cancelSubscription.mockResolvedValue({ id: 'sub-1', cancel_at_period_end: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('covers communications conversations and template creation', async () => {
    renderWithProviders(<Communications />);

    expect(await screen.findByText('Patient Communications')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Search messages...'), { target: { value: 'abcdef' } });
    fireEvent.click(screen.getByText(/Patient patient-/i));
    await waitFor(() => expect(mocks.selectConversation).toHaveBeenCalledWith('conversation-1'));

    fireEvent.change(screen.getByPlaceholderText('Type your message...'), { target: { value: 'Confirmed, thank you' } });
    fireEvent.keyDown(screen.getByPlaceholderText('Type your message...'), { key: 'Enter' });
    await waitFor(() => expect(mocks.sendConversationMessage).toHaveBeenCalledWith('conversation-1', expect.objectContaining({ content: 'Confirmed, thank you' })));

    fireEvent.click(screen.getByRole('button', { name: /new message/i }));
    fireEvent.change(screen.getByPlaceholderText('Appointment Reminder'), { target: { value: 'Post Visit Follow-up' } });
    fireEvent.change(screen.getByPlaceholderText(/Hi \[patient_name\]/i), { target: { value: 'Thanks for visiting [patient_name]' } });
    fireEvent.click(screen.getByRole('button', { name: /save template/i }));
    await waitFor(() => expect(mocks.createTemplate).toHaveBeenCalledWith(expect.objectContaining({ name: 'Post Visit Follow-up' })));
  });

  it('covers treatment plan create, edit, delete, and procedure workflows', async () => {
    renderWithProviders(<TreatmentPlans />);

    expect(await screen.findByText('Crown Plan')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /view crown plan/i }));
    await screen.findByRole('button', { name: /add procedure/i });
    fireEvent.click(screen.getByRole('button', { name: /add procedure/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.addProcedure).toHaveBeenCalledWith('plan-1', expect.objectContaining({ procedureName: 'Cleaning' })));
    fireEvent.click(await screen.findByRole('button', { name: /complete procedure/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.completeProcedure).toHaveBeenCalledWith('procedure-1'));
    fireEvent.click(await screen.findByRole('button', { name: /delete procedure/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.deleteProcedure).toHaveBeenCalledWith('procedure-1'));

    fireEvent.click(screen.getByRole('button', { name: /delete crown plan/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^cancel plan$/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.deletePlan).toHaveBeenCalledWith('plan-1'));

    fireEvent.click(screen.getByRole('button', { name: /^New Plan$/i }));
    fireEvent.click(screen.getByRole('button', { name: /submit new plan/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.createPlan).toHaveBeenCalledWith(expect.objectContaining({ title: 'Implant Plan' })));
    fireEvent.click(await screen.findByRole('button', { name: /save visual builder/i }));
    await waitFor(() => expect(mocks.treatmentPlanApi.updatePlan).toHaveBeenCalledWith(
      'plan-2',
      expect.objectContaining({ status: 'accepted' }),
      expect.objectContaining({ patientName: 'Ada Lovelace' }),
    ));
  });

  it('covers clinical note search, create, update, and delete workflows', async () => {
    const searchView = renderWithProviders(
      <Routes>
        <Route path="/notes" element={<ClinicalNotes />} />
        <Route path="/notes/:id" element={<ClinicalNotes />} />
      </Routes>,
      '/notes',
    );

    fireEvent.change(screen.getByPlaceholderText(/search by name or email/i), { target: { value: 'Ada' } });
    expect(await screen.findByText(/Ada Lovelace · ada@example.com/i)).toBeInTheDocument();
    searchView.unmount();

    renderWithProviders(
      <Routes>
        <Route path="/notes/:id" element={<ClinicalNotes />} />
      </Routes>,
      '/notes/patient-1',
    );

    expect(await screen.findByText('Existing clinical note')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /new note/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New note content' } });
    fireEvent.click(screen.getByRole('button', { name: /save note/i }));
    await waitFor(() => expect(mocks.clinicalNotesApi.create).toHaveBeenCalledWith(expect.objectContaining({ content: 'New note content' })));

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons.find((button) => button.querySelector('svg.lucide-pencil'))!);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Updated note content' } });
    fireEvent.click(screen.getByRole('button', { name: /update note/i }));
    await waitFor(() => expect(mocks.clinicalNotesApi.update).toHaveBeenCalledWith('note-2', expect.objectContaining({ content: 'Updated note content' })));

    fireEvent.click(screen.getAllByRole('button').find((button) => button.querySelector('svg.lucide-trash2'))!);
    fireEvent.click((await screen.findAllByText(/^Delete$/i)).at(-1)!);
    await waitFor(() => expect(mocks.clinicalNotesApi.delete).toHaveBeenCalledWith('note-1'));
  });

  it('covers subscription plan selection and cancellation', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Subscriptions />);

    expect(screen.getByText('$99.00')).toBeInTheDocument();
    expect(screen.getByText('Active Subscription')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Subscribe$/i }));
    fireEvent.click(await screen.findByRole('button', { name: /start free trial/i }));
    await waitFor(() => expect(mocks.createSubscription).toHaveBeenCalledWith({ plan_id: 'plan-basic', trial_period_days: 14 }));

    await user.click(screen.getByRole('tab', { name: /my subscription/i }));
    expect(await screen.findByText('Current Subscription')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /cancel subscription/i }));
    fireEvent.change(screen.getByLabelText(/reason for canceling/i), { target: { value: 'Switching plans' } });
    fireEvent.click(screen.getByRole('button', { name: /^Cancel Subscription$/i }));
    await waitFor(() => expect(mocks.cancelSubscription).toHaveBeenCalledWith({
      id: 'sub-1',
      data: { cancel_at_period_end: true, reason: 'Switching plans' },
    }));
  });
});