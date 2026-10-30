import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import EnterpriseHQ from '@/pages/EnterpriseHQ';
import { server } from '@/test/mocks/server';

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <EnterpriseHQ />
    </QueryClientProvider>,
  );
}

describe('EnterpriseHQ group analytics', () => {
  it('renders server-backed consolidated and location metrics', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: /enterprise hq/i })).toBeInTheDocument();
    expect(await screen.findByText('32,500')).toBeInTheDocument();
    expect(screen.getByText('Bright Smile Dental')).toBeInTheDocument();
    expect(screen.getByText('Harbor Dental Care')).toBeInTheDocument();
    expect(screen.getByText('Group scope')).toBeInTheDocument();
    expect(screen.queryByText(/practice analytics/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/multi-location consolidation is not enabled/i)).not.toBeInTheDocument();
  });

  it('fails closed when the group analytics endpoint is not authorized', async () => {
    server.use(
      http.get('/api/v1/enterprise/group/analytics', () =>
        HttpResponse.json({ detail: 'Enterprise access required' }, { status: 403 }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/group analytics unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText('32,500')).not.toBeInTheDocument();
  });
});
