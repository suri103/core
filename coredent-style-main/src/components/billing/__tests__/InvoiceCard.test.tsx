import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InvoiceCard } from '../InvoiceCard';
import type { Invoice } from '@/types/billing';

vi.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ user: null }),
}));

const baseInvoice: Invoice = {
  id: 'inv-1',
  invoiceNumber: 'INV-001',
  patientId: 'p-1',
  patientName: 'John Doe',
  patientEmail: 'john@example.com',
  patientPhone: '555-0100',
  lineItems: [],
  subtotal: 120,
  taxRate: 0,
  taxAmount: 0,
  total: 120,
  amountPaid: 0,
  balance: 120,
  status: 'pending',
  issueDate: '2026-06-01',
  dueDate: '2026-07-01',
  payments: [],
  notes: '',
  createdAt: '2026-06-01T00:00:00Z',
  updatedAt: '2026-06-01T00:00:00Z',
};

function renderCard(invoice: Invoice = baseInvoice, overrides: Record<string, unknown> = {}) {
  const props = {
    onView: vi.fn(),
    onRecordPayment: vi.fn(),
    onDownload: vi.fn(),
    onSend: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  const result = render(<InvoiceCard invoice={invoice} {...props} />);
  return { ...props, unmount: result.unmount };
}

describe('InvoiceCard', () => {
  it('renders real patient, amount, balance, and dates', () => {
    renderCard();
    expect(screen.getByText('INV-001')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getAllByText('$120.00').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Issued: 2026-06-01/)).toBeInTheDocument();
    expect(screen.getByText(/Due: 2026-07-01/)).toBeInTheDocument();
  });

  it('formats currency and colors outstanding and zero balances', () => {
    const { unmount } = renderCard({ ...baseInvoice, total: 1234.5, balance: 1234.5 });
    expect(screen.getAllByText('$1,234.50').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('$1,234.50', { selector: '.text-rose-500' })).toBeInTheDocument();
    unmount();
    renderCard({ ...baseInvoice, status: 'paid', balance: 0 });
    expect(screen.getByText('$0.00').className).toContain('text-emerald-500');
  });

  it.each([
    ['paid', 'bg-emerald-500'],
    ['partially_paid', 'bg-sky-500'],
    ['pending', 'bg-amber-500'],
    ['overdue', 'bg-rose-500'],
    ['cancelled', 'bg-neutral-500'],
    ['draft', 'bg-blue-500'],
  ] as const)('uses the backend status %s with the correct color', (status, colorClass) => {
    renderCard({ ...baseInvoice, status });
    const badge = screen.getByText(status.replace('_', ' '));
    expect(badge.className).toContain(colorClass);
  });

  it('shows payment actions only for payable backend statuses', () => {
    const { unmount } = renderCard({ ...baseInvoice, status: 'partially_paid' });
    expect(screen.getByRole('button', { name: /^pay$/i })).toBeInTheDocument();
    unmount();
    renderCard({ ...baseInvoice, status: 'draft' });
    expect(screen.queryByRole('button', { name: /^pay$/i })).not.toBeInTheDocument();
  });

  it('calls view and payment actions with the invoice', () => {
    const onView = vi.fn();
    const onRecordPayment = vi.fn();
    renderCard(baseInvoice, { onView, onRecordPayment });
    fireEvent.click(screen.getByRole('button', { name: /details/i }));
    fireEvent.click(screen.getByRole('button', { name: /^pay$/i }));
    expect(onView).toHaveBeenCalledWith(baseInvoice);
    expect(onRecordPayment).toHaveBeenCalledWith(baseInvoice);
  });

  it('offers issuing only for drafts and labels soft deletion as cancellation', async () => {
    const user = userEvent.setup();
    renderCard({ ...baseInvoice, status: 'draft' });
    await user.click(screen.getByRole('button', { name: /open menu/i }));
    expect(await screen.findByText('Send Invoice')).toBeInTheDocument();
    expect(await screen.findByText('Cancel Invoice')).toBeInTheDocument();
  });

  it('hides cancellation for paid and cancelled invoices', () => {
    renderCard({ ...baseInvoice, status: 'paid' });
    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    expect(screen.queryByText('Cancel Invoice')).not.toBeInTheDocument();
    expect(screen.queryByText('Record Payment')).not.toBeInTheDocument();
  });
});
