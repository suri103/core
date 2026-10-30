import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import ReferralHub from '@/pages/ReferralHub';

vi.mock('@/services/referralsApi', () => ({
  referralsApi: {
    list: vi.fn().mockResolvedValue({ referrals: [{ id: 'ref-1', patient_id: 'patient-1', patient: { first_name: 'Ada', last_name: 'Lovelace' }, referral_type: 'Endodontics', status: 'pending', referral_date: '2026-07-01', notes: 'Review tooth 14' }], count: 1 }),
  },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<BrowserRouter><QueryClientProvider client={client}><ReferralHub /></QueryClientProvider></BrowserRouter>);
}

describe('ReferralHub live queue', () => {
  it('renders persisted referrals from the service boundary', async () => {
    renderPage();
    expect(await screen.findByText('Referral Management')).toBeInTheDocument();
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
  });
});