import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InsuranceList } from '../InsuranceList';
import { insuranceApi } from '@/services/insuranceApi';

vi.mock('@/services/insuranceApi', () => ({
  insuranceApi: {
    getCarriers: vi.fn(),
  },
}));

const mockInsuranceApi = vi.mocked(insuranceApi);

const carriers = [
  {
    id: 'carrier-1',
    name: 'Delta Dental',
    phone: '555-1111',
    email: 'claims@delta.example',
    payerId: 'DELTA-01',
    addressLine1: '1 Dental Way',
    city: 'Austin',
    state: 'TX',
    zipCode: '78701',
    isActive: true,
  },
  {
    id: 'carrier-2',
    name: 'Aetna',
    phone: '',
    email: '',
    payerId: '',
    isActive: false,
  },
];

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <InsuranceList />
    </QueryClientProvider>,
  );
}

describe('InsuranceList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders carriers, filters them, and supports create and edit', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    const onCreate = vi.fn();

    mockInsuranceApi.getCarriers.mockResolvedValue(carriers as never);

    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={client}>
        <InsuranceList onEdit={onEdit} onCreate={onCreate} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Delta Dental')).toBeInTheDocument();
    expect(screen.getByText('Aetna')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('claims@delta.example')).toBeInTheDocument();
    expect(screen.getByText('1 Dental Way, Austin, TX 78701')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /add carrier/i }));
    expect(onCreate).toHaveBeenCalledTimes(1);

    await user.type(screen.getByPlaceholderText(/search carriers/i), 'delta');
    expect(screen.getByText('Delta Dental')).toBeInTheDocument();
    expect(screen.queryByText('Aetna')).not.toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: /edit/i })[0]);
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 'carrier-1' }));
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('shows the empty state when there are no carriers', async () => {
    mockInsuranceApi.getCarriers.mockResolvedValue([] as never);

    renderWithClient();

    expect(await screen.findByText('No insurance carriers yet')).toBeInTheDocument();
  });

  it('shows the error state when carriers cannot be loaded', async () => {
    mockInsuranceApi.getCarriers.mockRejectedValue(new Error('boom'));

    renderWithClient();

    expect(await screen.findByText('Failed to load insurance carriers')).toBeInTheDocument();
  });
});
