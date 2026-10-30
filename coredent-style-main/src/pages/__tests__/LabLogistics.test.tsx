import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import LabLogistics from '@/pages/LabLogistics';

vi.mock('@/services/labsApi', () => ({
  labsApi: {
    listCases: vi.fn().mockResolvedValue({ cases: [{ id: 'case-1', case_number: 'LAB-1', patient_id: 'patient-1', case_type: 'crown', status: 'shipped', due_date: '2026-07-10', tracking_number: 'TRACK-1' }], count: 1 }),
  },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<BrowserRouter><QueryClientProvider client={client}><LabLogistics /></QueryClientProvider></BrowserRouter>);
}

describe('LabLogistics live cases', () => {
  it('renders persisted lab cases from the service boundary', async () => {
    renderPage();
    expect(await screen.findByText('Lab Cases')).toBeInTheDocument();
    expect(await screen.findAllByText('LAB-1')).toHaveLength(2);
    expect(screen.getAllByText('shipped')).toHaveLength(2);
  });
});