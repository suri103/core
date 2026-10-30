import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';

const state = vi.hoisted(() => ({
  toast: vi.fn(),
  invalidateQueries: vi.fn(),
  createClaim: vi.fn(),
  submitClaim: vi.fn(),
  carriers: [{
    id: 'carrier-1',
    name: 'Delta Dental',
    payerId: 'DELTA',
    phone: '555-1000',
    ediEnabled: true,
    isActive: true,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
  }],
  claimsPage: {
    items: [{
      id: 'claim-1',
      practiceId: 'practice-1',
      patientId: 'patient-1',
      patientInsuranceId: 'policy-1',
      carrierId: 'carrier-1',
      claimNumber: 'CLM-001',
      status: 'draft',
      serviceDate: '2026-06-01',
      billedAmount: 100,
      deductibleAmount: 0,
      copayAmount: 0,
      paidAmount: 0,
      patientResponsibility: 0,
      procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 100 }],
      diagnosisCodes: [],
      outstandingBalance: 100,
      createdAt: '2026-06-01T00:00:00.000Z',
      updatedAt: '2026-06-01T00:00:00.000Z',
    }, {
      id: 'claim-2',
      practiceId: 'practice-1',
      patientId: 'patient-2',
      patientInsuranceId: 'policy-2',
      carrierId: 'carrier-2',
      claimNumber: 'CLM-002',
      status: 'partially_approved',
      serviceDate: '2026-06-02',
      submissionDate: '2026-06-03',
      billedAmount: 300,
      allowedAmount: 250,
      deductibleAmount: 0,
      copayAmount: 0,
      paidAmount: 100,
      patientResponsibility: 150,
      procedureCodes: [{ code: 'D2740', description: 'Crown', fee: 300 }],
      diagnosisCodes: [],
      outstandingBalance: 200,
      createdAt: '2026-06-02T00:00:00.000Z',
      updatedAt: '2026-06-03T00:00:00.000Z',
    }],
    count: 2,
    total: 2,
    limit: 50,
    offset: 0,
    nextOffset: null,
  },
  preAuthPage: {
    items: [{
      id: 'auth-1',
      patientId: 'patient-1',
      patientInsuranceId: 'policy-1',
      authorizationNumber: 'AUTH-1',
      status: 'approved',
      requestDate: '2026-06-01',
      procedureCodes: [{ code: 'D1110', description: 'Cleaning', fee: 100 }],
      estimatedCost: 100,
      createdAt: '2026-06-01T00:00:00.000Z',
      updatedAt: '2026-06-01T00:00:00.000Z',
    }],
    count: 1,
    total: 1,
    limit: 50,
    offset: 0,
    nextOffset: null,
  },
}));

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQuery: (options: { queryKey: unknown[] }) => {
      const resource = options.queryKey[1];
      if (resource === 'carriers') return { data: state.carriers, isLoading: false, isError: false };
      if (resource === 'claims') return { data: state.claimsPage, isLoading: false, isError: false };
      if (resource === 'preAuths') return { data: state.preAuthPage, isLoading: false, isError: false };
      return { data: undefined, isLoading: false, isError: false };
    },
    useQueryClient: () => ({ invalidateQueries: state.invalidateQueries }),
  };
});

vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: state.toast }) }));
vi.mock('@/services/insuranceApi', () => ({
  insuranceApi: {
    getCarriers: vi.fn(),
    getClaims: vi.fn(),
    getPreAuthorizations: vi.fn(),
    createClaim: state.createClaim,
    submitClaim: state.submitClaim,
  },
}));

import Insurance from '../Insurance';

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter><AuthProvider>{children}</AuthProvider></BrowserRouter>
  );
}

describe('Insurance Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.createClaim.mockResolvedValue({ ...state.claimsPage.items[0], id: 'claim-new' });
    state.submitClaim.mockResolvedValue({ ...state.claimsPage.items[0], status: 'submitted' });
  });

  it('renders real claim identifiers, statuses, and available workflow tabs', async () => {
    render(<Insurance />, { wrapper: createWrapper() });

    expect(await screen.findByText('Claim CLM-001')).toBeInTheDocument();
    expect(screen.getByText('Claim CLM-002')).toBeInTheDocument();
    expect(screen.getByText('Partially approved')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Claims' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Carriers & Pre-Authorizations' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /EOB/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Total Paid')).not.toBeInTheDocument();
  });

  it('filters loaded claims, shows coverage data, submits, and creates a backend-valid claim', async () => {
    const user = userEvent.setup();
    render(<Insurance />, { wrapper: createWrapper() });

    await user.type(screen.getByPlaceholderText(/search loaded claims/i), 'patient-1');
    expect(screen.getByText('Claim CLM-001')).toBeInTheDocument();
    expect(screen.queryByText('Claim CLM-002')).not.toBeInTheDocument();
    await user.clear(screen.getByPlaceholderText(/search loaded claims/i));

    await user.click(screen.getByRole('tab', { name: 'Carriers & Pre-Authorizations' }));
    expect(screen.getByText('Delta Dental')).toBeInTheDocument();
    expect(screen.getByText(/Authorization AUTH-1/)).toBeInTheDocument();
    expect(screen.getByText(/Patient ID: patient-1 · Policy ID: policy-1/)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Claims' }));
    await user.click(screen.getByRole('button', { name: /^submit$/i }));
    await waitFor(() => expect(state.submitClaim).toHaveBeenCalledWith('claim-1'));

    await user.click(screen.getByRole('button', { name: /new claim/i }));
    await user.type(screen.getByLabelText(/patient insurance policy id/i), 'policy-1');
    await user.type(screen.getByLabelText(/service date/i), '2026-06-27');
    await user.type(screen.getByLabelText(/^code \*$/i), 'D1110');
    await user.type(screen.getByLabelText(/billed amount/i), '150');
    await user.type(screen.getByLabelText(/description/i), 'Adult cleaning');
    await user.type(screen.getByLabelText(/notes/i), 'Created in test');
    await user.click(screen.getByRole('button', { name: /create draft/i }));

    await waitFor(() => expect(state.createClaim).toHaveBeenCalledWith({
      patientInsuranceId: 'policy-1',
      serviceDate: '2026-06-27',
      billedAmount: 150,
      procedureCodes: [{ code: 'D1110', description: 'Adult cleaning', fee: 150 }],
      notes: 'Created in test',
    }));
    expect(state.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Claim Created' }));
    expect(state.invalidateQueries).toHaveBeenCalled();
  });
});
