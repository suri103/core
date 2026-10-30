import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Inventory from '../Inventory';

vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({
    hasRole: (...roles: string[]) => roles.includes('owner'),
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <BrowserRouter>
      <QueryClientProvider client={client}>
        <Inventory />
      </QueryClientProvider>
    </BrowserRouter>,
  );
}

describe('Inventory Page', () => {
  it('renders the live page heading and write entry point', () => {
    renderPage();
    expect(screen.getByRole('heading', { level: 1, name: /inventory management/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add item/i })).toBeInTheDocument();
  });

  it('renders inventory data returned by the API instead of sample rows', async () => {
    renderPage();
    expect(await screen.findByText('Nitrile gloves')).toBeInTheDocument();
    expect(screen.getByText('Composite resin')).toBeInTheDocument();
    expect(screen.getByText('Total items')).toBeInTheDocument();
    expect(screen.getByText('Open alerts')).toBeInTheDocument();
  });

  it('uses the live search, low-stock, and alert views', async () => {
    const user = userEvent.setup();
    renderPage();

    const searchInput = screen.getByPlaceholderText(/search by name or sku/i);
    await user.type(searchInput, 'gloves');
    await waitFor(() => expect(screen.getByText('Nitrile gloves')).toBeInTheDocument());
    expect(screen.queryByText('Composite resin')).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /low stock/i }));
    expect(await screen.findByText('Nitrile gloves')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /alerts/i }));
    expect(await screen.findByText(/nitrile gloves are at or below/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resolve/i })).toBeInTheDocument();
  });
});
