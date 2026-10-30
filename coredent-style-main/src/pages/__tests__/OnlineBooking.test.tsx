import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OnlineBooking from '@/pages/OnlineBooking';

vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({
    hasRole: (...roles: string[]) => roles.includes('dentist'),
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <BrowserRouter>
      <QueryClientProvider client={client}>
        <OnlineBooking />
      </QueryClientProvider>
    </BrowserRouter>,
  );
}

describe('OnlineBooking Page', () => {
  it('renders live requests and waitlist data for a dentist', async () => {
    renderPage();

    expect(screen.getByRole('heading', { name: /online booking/i })).toBeInTheDocument();
    expect(await screen.findByText('Alex Morgan')).toBeInTheDocument();
    expect(screen.getByText('Pending requests')).toBeInTheDocument();
    expect(screen.queryByText(/patient booking link/i)).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('tab', { name: /waitlist/i }));
    expect(await screen.findByText('Jamie Lee')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /notify/i })).toBeInTheDocument();
  });
});
