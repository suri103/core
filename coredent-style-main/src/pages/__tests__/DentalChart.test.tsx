import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { dentalChartApi } from '@/services/dentalChartApi';
import DentalChart from '../DentalChart';
import type { DentalChart as DentalChartType } from '@/types/dentalChart';

const { addProcedureDialogMock, aiAssistantMock, dentalChartViewMock, toothDetailsPanelMock, toastMock } = vi.hoisted(() => ({
  addProcedureDialogMock: vi.fn(),
  aiAssistantMock: vi.fn(),
  dentalChartViewMock: vi.fn(),
  toothDetailsPanelMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/services/dentalChartApi', () => ({
  dentalChartApi: {
    getChart: vi.fn(),
    updateToothCondition: vi.fn(),
    addProcedure: vi.fn(),
    updateProcedureStatus: vi.fn(),
    deleteProcedure: vi.fn(),
  },
}));

vi.mock('@/components/chart/DentalChartView', () => ({
  DentalChartView: (props: {
    teeth: Array<{ number: number; name: string }>;
    selectedTooth: number | null;
    onSelectTooth: (toothNumber: number) => void;
  }) => {
    dentalChartViewMock(props);
    return (
      <div>
        <div data-testid="dental-chart-view">Dental chart view</div>
        <div data-testid="selected-tooth">{props.selectedTooth ?? 'none'}</div>
        {props.teeth.map((tooth) => (
          <button key={tooth.number} type="button" onClick={() => props.onSelectTooth(tooth.number)}>
            Tooth {tooth.number}
          </button>
        ))}
      </div>
    );
  },
}));

vi.mock('@/components/chart/ToothDetailsPanel', () => ({
  ToothDetailsPanel: (props: {
    tooth: { number: number; condition: string; procedures?: Array<{ id: string; status: string }> } | null;
    onAddProcedure: () => void;
    onUpdateCondition: (condition: string) => void;
    onUpdateProcedureStatus: (procedureId: string, status: string) => void;
    onDeleteProcedure: (procedureId: string) => void;
  }) => {
    toothDetailsPanelMock(props);
    if (!props.tooth) {
      return <div data-testid="tooth-details">No tooth selected</div>;
    }

    return (
      <div data-testid="tooth-details">
        <div>Tooth #{props.tooth.number}</div>
        <div>Condition: {props.tooth.condition}</div>
        <div>Procedures: {props.tooth.procedures?.length ?? 0}</div>
        <button type="button" onClick={() => props.onUpdateCondition('decay')}>Set decay</button>
        <button type="button" onClick={props.onAddProcedure}>Add procedure</button>
        <button type="button" onClick={() => props.onUpdateProcedureStatus('proc-1', 'completed')}>Mark completed</button>
        <button type="button" onClick={() => props.onDeleteProcedure('proc-1')}>Delete procedure</button>
      </div>
    );
  },
}));

vi.mock('@/components/chart/AddProcedureDialog', () => ({
  AddProcedureDialog: (props: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (data: {
      code: string;
      description: string;
      cost: number;
      status: 'planned' | 'completed' | 'cancelled';
      date: string;
    }) => Promise<void> | void;
  }) => {
    addProcedureDialogMock(props);
    if (!props.open) {
      return null;
    }

    return (
      <div role="dialog" aria-label="Add Procedure">
        <button
          type="button"
          onClick={() =>
            void props.onSubmit({
              code: 'D1110',
              description: 'Cleaning',
              cost: 125,
              status: 'planned',
              date: '2026-06-27',
            })
          }
        >
          Submit procedure
        </button>
        <button type="button" onClick={() => props.onOpenChange(false)}>
          Close
        </button>
      </div>
    );
  },
}));

vi.mock('@/components/chart/AIClinicalAssistant', () => ({
  AIClinicalAssistant: (props: { onApplyFinding: (tooth: number, finding: string) => void }) => {
    aiAssistantMock(props);
    return (
      <button type="button" onClick={() => props.onApplyFinding(8, 'Caries noted on tooth 8')}>
        Apply AI finding
      </button>
    );
  },
}));

const mockChart: DentalChartType = {
  id: 'chart-1',
  patientId: 'p-1',
  patientName: 'John Doe',
  teeth: [
    { number: 14, name: 'Upper Right First Molar', condition: 'sound', procedures: [] },
    { number: 8, name: 'Upper Right Central Incisor', condition: 'decay', procedures: [{ id: 'proc-1', code: 'D1110', description: 'Existing cleaning', cost: 110, date: '2026-06-10', status: 'planned' }] },
  ],
  updatedAt: '2026-06-01T00:00:00Z',
};

const refreshedChart: DentalChartType = {
  ...mockChart,
  updatedAt: '2026-06-20T00:00:00Z',
  teeth: [
    { number: 14, name: 'Upper Right First Molar', condition: 'sound', procedures: [] },
    { number: 8, name: 'Upper Right Central Incisor', condition: 'decay', procedures: [] },
  ],
};

function renderWithPatient(patientId: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/chart?patientId=${patientId}`]}>
        <Routes>
          <Route path="/chart" element={<DentalChart />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DentalChart page', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(dentalChartApi.getChart).mockResolvedValue(mockChart);
    vi.mocked(dentalChartApi.updateToothCondition).mockResolvedValue(mockChart);
    vi.mocked(dentalChartApi.addProcedure).mockResolvedValue({ id: 'proc-new', code: 'D1110', description: 'Cleaning', cost: 125, date: '2026-06-27', status: 'planned' } as never);
    vi.mocked(dentalChartApi.updateProcedureStatus).mockResolvedValue(undefined);
    vi.mocked(dentalChartApi.deleteProcedure).mockResolvedValue(undefined);
  });

  it('renders the page heading, subtitle, and loaded patient info', async () => {
    renderWithPatient('p-1');

    expect(screen.getByText('Dental Chart')).toBeInTheDocument();
    expect(screen.getByText(/Interactive tooth charting/)).toBeInTheDocument();
    expect(await screen.findByText('John Doe')).toBeInTheDocument();
    expect(screen.getByTestId('dental-chart-view')).toBeInTheDocument();
  });

  it('shows an alert when no patient is selected', async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/chart']}>
          <Routes>
            <Route path="/chart" element={<DentalChart />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Dental chart unavailable');
    expect(screen.getByText('No chart data available')).toBeInTheDocument();
  });

  it('lets the user select a tooth, update it, add procedures, and apply an AI finding', async () => {
    const user = userEvent.setup();
    renderWithPatient('p-1');

    await screen.findByText('John Doe');

    await user.click(screen.getByRole('button', { name: 'Tooth 8' }));
    expect(screen.getByTestId('selected-tooth')).toHaveTextContent('8');
    expect(screen.getByTestId('tooth-details')).toHaveTextContent('Tooth #8');

    await user.click(screen.getByRole('button', { name: 'Set decay' }));
    await waitFor(() => expect(dentalChartApi.updateToothCondition).toHaveBeenCalledWith('p-1', 8, 'decay'));
    expect(screen.getByTestId('tooth-details')).toHaveTextContent('Condition: decay');

    await user.click(screen.getByRole('button', { name: 'Add procedure' }));
    expect(screen.getByRole('dialog', { name: 'Add Procedure' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit procedure' }));
    await waitFor(() => expect(dentalChartApi.addProcedure).toHaveBeenCalledWith('p-1', 8, expect.objectContaining({ code: 'D1110', description: 'Cleaning' })));
    expect(screen.getByTestId('tooth-details')).toHaveTextContent('Procedures: 2');

    await user.click(screen.getByRole('button', { name: 'Mark completed' }));
    await waitFor(() => expect(dentalChartApi.updateProcedureStatus).toHaveBeenCalledWith('p-1', 8, 'proc-1', 'completed'));

    await user.click(screen.getByRole('button', { name: 'Delete procedure' }));
    await waitFor(() => expect(dentalChartApi.deleteProcedure).toHaveBeenCalledWith('p-1', 8, 'proc-1'));

    await user.click(screen.getByRole('button', { name: 'Apply AI finding' }));
    expect(screen.getByTestId('selected-tooth')).toHaveTextContent('8');
  });

  it('refreshes the chart and clears the current selection', async () => {
    const user = userEvent.setup();
    vi.mocked(dentalChartApi.getChart)
      .mockResolvedValueOnce(mockChart)
      .mockResolvedValueOnce(refreshedChart);

    renderWithPatient('p-1');

    await screen.findByText('John Doe');
    await user.click(screen.getByRole('button', { name: 'Tooth 8' }));
    expect(screen.getByTestId('selected-tooth')).toHaveTextContent('8');

    await user.click(screen.getByRole('button', { name: /refresh/i }));
    await waitFor(() => expect(dentalChartApi.getChart).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('selected-tooth')).toHaveTextContent('none');
    expect(screen.getByText(/20\/06\/2026/)).toBeInTheDocument();
  });
});
