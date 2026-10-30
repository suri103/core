import { beforeEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { billingApi } from '../billingApi';
import { server } from '@/test/mocks/server';
import type { Invoice } from '@/types/billing';

const invoiceWire = {
  id: 'inv-1',
  practice_id: 'practice-1',
  patient_id: 'patient-1',
  patient_name: 'John Doe',
  patient_email: 'john@example.com',
  patient_phone: '555-0100',
  invoice_number: 'INV-001',
  status: 'pending',
  line_items: [
    {
      description: 'Adult prophylaxis',
      quantity: 1,
      unit_price: '120.00',
      total: '120.00',
    },
  ],
  tax_rate: '0.050000',
  due_date: '2026-07-01',
  notes: 'First visit',
  subtotal: '120.00',
  tax: '6.00',
  total: '126.00',
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
  amount_paid: '0.00',
  balance_due: '126.00',
  payments: [],
} as const;

const paymentWire = {
  id: 'pay-1',
  invoice_id: 'inv-1',
  patient_id: 'patient-1',
  amount: '126.00',
  payment_method: 'card',
  transaction_id: 'txn-1',
  notes: null,
  status: 'completed',
  refunded_amount: '0.00',
  created_at: '2026-06-22T12:00:00Z',
} as const;

function paidInvoiceWire() {
  return {
    ...invoiceWire,
    status: 'paid',
    amount_paid: '126.00',
    balance_due: '0.00',
    payments: [paymentWire],
  };
}

describe('billingApi', () => {
  beforeEach(() => server.resetHandlers());

  it('maps invoice envelopes, Decimal strings, patient data, and payments', async () => {
    server.use(
      http.get('/api/v1/billing/invoices/', () => HttpResponse.json({
        invoices: [paidInvoiceWire()],
        count: 1,
        total: 1,
        limit: 50,
        offset: 0,
        next_offset: null,
      })),
    );

    const [invoice] = await billingApi.getInvoices();
    expect(invoice).toMatchObject({
      patientName: 'John Doe',
      taxRate: 5,
      taxAmount: 6,
      total: 126,
      balance: 0,
      issueDate: '2026-06-01',
    });
    expect(invoice.payments[0]).toMatchObject({
      id: 'pay-1',
      method: 'card',
      amount: 126,
      reference: 'txn-1',
    });
  });

  it('maps a bare invoice array and passes backend filter names', async () => {
    server.use(
      http.get('/api/v1/billing/invoices/', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('status')).toBe('paid');
        expect(url.searchParams.get('patient_id')).toBe('patient-1');
        expect(url.searchParams.get('limit')).toBe('25');
        return HttpResponse.json([invoiceWire]);
      }),
    );

    const result = await billingApi.getInvoices({
      status: 'paid',
      patientId: 'patient-1',
      limit: 25,
    });
    expect(result).toHaveLength(1);
  });

  it('maps a single invoice and throws for a missing one', async () => {
    server.use(
      http.get('/api/v1/billing/invoices/inv-1', () => HttpResponse.json(invoiceWire)),
      http.get('/api/v1/billing/invoices/missing', () =>
        HttpResponse.json({ message: 'Not found' }, { status: 404 })),
    );

    await expect(billingApi.getInvoice('inv-1')).resolves.toMatchObject({ id: 'inv-1' });
    await expect(billingApi.getInvoice('missing')).rejects.toThrow();
  });

  it('maps the real backend summary and derives status counts', async () => {
    server.use(
      http.get('/api/v1/billing/summary', () => HttpResponse.json({
        total_invoices: 5,
        total_revenue: 1000,
        total_tax: 50,
        total_payments: 2,
        total_collected: 400,
        outstanding_balance: 600,
        status_breakdown: [
          { status: 'pending', count: 3, amount: 700 },
          { status: 'overdue', count: 1, amount: 300 },
        ],
      })),
    );

    const result = await billingApi.getSummary();
    expect(result).toMatchObject({
      totalInvoices: 5,
      totalCollected: 400,
      outstandingBalance: 600,
      pendingCount: 3,
      pendingAmount: 700,
      overdueCount: 1,
    });
  });

  it('creates a backend-valid invoice with cent-safe item totals and percentage conversion', async () => {
    server.use(
      http.post('/api/v1/billing/invoices/', async ({ request }) => {
        const body = await request.json() as any;
        expect(body).toMatchObject({
          patient_id: 'patient-1',
          tax_rate: 0.05,
          line_items: [{
            description: 'Exam',
            quantity: 3,
            unit_price: 10.1,
            total: 30.3,
          }],
        });
        return HttpResponse.json({ ...invoiceWire, id: 'inv-2' });
      }),
    );

    const result = await billingApi.createInvoice({
      patientId: 'patient-1',
      lineItems: [{ description: 'Exam', quantity: 3, unitPrice: 10.1 }],
      taxRatePercent: 5,
      dueDate: '2026-08-01',
    });
    expect(result.id).toBe('inv-2');
  });

  it('omits tax rate when preferences are unavailable so the backend default applies', async () => {
    server.use(
      http.post('/api/v1/billing/invoices/', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        expect(body).not.toHaveProperty('tax_rate');
        return HttpResponse.json(invoiceWire);
      }),
    );

    await billingApi.createInvoice({
      patientId: 'patient-1',
      lineItems: [{ description: 'Exam', quantity: 1, unitPrice: 100 }],
    });
  });

  it('rejects an empty invoice before making a request', async () => {
    await expect(billingApi.createInvoice({
      patientId: 'patient-1',
      lineItems: [],
    })).rejects.toThrow('at least one line item');
  });

  it('uses backend status vocabulary for issuing an invoice', async () => {
    server.use(
      http.put('/api/v1/billing/invoices/inv-1', async ({ request }) => {
        expect(await request.json()).toEqual({ status: 'pending' });
        return HttpResponse.json(invoiceWire);
      }),
    );
    await expect(billingApi.updateStatus('inv-1', 'pending')).resolves.toMatchObject({
      status: 'pending',
    });
  });

  it('returns the real payment id and refreshed invoice after recording payment', async () => {
    server.use(
      http.get('/api/v1/billing/invoices/inv-1', () => HttpResponse.json(paidInvoiceWire())),
      http.post('/api/v1/billing/payments/', async ({ request }) => {
        const body = await request.json() as any;
        expect(body).toMatchObject({
          invoice_id: 'inv-1',
          patient_id: 'patient-1',
          amount: 126,
          payment_method: 'card',
          transaction_id: 'txn-1',
        });
        return HttpResponse.json(paymentWire);
      }),
    );

    const result = await billingApi.recordPayment('inv-1', {
      patientId: 'patient-1',
      amount: 126,
      method: 'card',
      reference: 'txn-1',
    });
    expect(result.payment.id).toBe('pay-1');
    expect(result.invoice.status).toBe('paid');
  });

  it('surfaces payment failures', async () => {
    server.use(
      http.post('/api/v1/billing/payments/', () =>
        HttpResponse.json({ message: 'Recording failed' }, { status: 400 })),
    );
    await expect(billingApi.recordPayment('inv-1', {
      patientId: 'patient-1',
      amount: 10,
      method: 'cash',
      reference: 'cash-drawer-001',
    })).rejects.toThrow('Recording failed');
  });

  it('soft-cancels an invoice through the backend delete route', async () => {
    server.use(
      http.delete('/api/v1/billing/invoices/inv-1', () =>
        HttpResponse.json({ message: 'Invoice cancelled successfully' })),
    );
    await expect(billingApi.cancelInvoice('inv-1')).resolves.toBeUndefined();
  });

  it('generates truthful escaped receipt HTML from real contract fields', () => {
    const invoice: Invoice = {
      id: 'inv-1',
      patientId: 'patient-1',
      patientName: '<script>John</script>',
      patientEmail: 'john@example.com',
      invoiceNumber: 'INV-001',
      status: 'paid',
      lineItems: [{ description: '<img src=x>', quantity: 1, unitPrice: 120, total: 120 }],
      subtotal: 120,
      taxRate: 5,
      taxAmount: 6,
      total: 126,
      amountPaid: 126,
      balance: 0,
      issueDate: '2026-06-01',
      dueDate: '2026-07-01',
      payments: [{
        id: 'pay-1',
        invoiceId: 'inv-1',
        patientId: 'patient-1',
        date: '2026-06-22',
        method: 'card',
        reference: 'txn-1',
        amount: 126,
        refundedAmount: 0,
        status: 'completed',
      }],
      createdAt: '2026-06-01T00:00:00Z',
      updatedAt: '2026-06-01T00:00:00Z',
    };

    const html = billingApi.generateReceiptHTML(invoice);
    expect(html).toContain('PAID IN FULL');
    expect(html).toContain('Payment History');
    expect(html).toContain('Tax (5%):');
    expect(html).toContain('&lt;script&gt;John&lt;/script&gt;');
    expect(html).not.toContain('<img src=x>');
    expect(html).not.toContain('123 Dental Street');
  });
});
