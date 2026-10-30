// ============================================
// CoreDent PMS - Billing API Service
// Explicitly maps the backend billing wire contract into frontend view models.
// ============================================

import type {
  BillingSummary,
  BillingStatusBreakdown,
  Invoice,
  InvoiceLineItem,
  InvoicePayment,
  InvoiceStatus,
  PaymentMethod,
  PaymentStatus,
  RecordPaymentResult,
} from '@/types/billing';
import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';
import { formatCurrency } from '@/lib/utils';

type MoneyWire = number | string;

interface LineItemWire {
  description: string;
  quantity: number;
  unitPrice: MoneyWire;
  total: MoneyWire;
}

interface PaymentWire {
  id: string;
  invoiceId: string;
  patientId: string;
  amount: MoneyWire;
  paymentMethod: PaymentMethod;
  transactionId?: string | null;
  notes?: string | null;
  status: PaymentStatus;
  refundedAmount: MoneyWire;
  createdAt: string;
}

/** Wire shape of POST /billing/payments/{id}/refund (currency units, same as recordPayment). */
// /billing responses are converted to camelCase at the ApiClient boundary
// (domainContract.normalizeResponsePayload), so these keys must match what the
// client returns. Reading snake_case here produced undefined for every field:
// the refund succeeded server-side, the invoice refetch hit
// /billing/invoices/undefined, and the UI reported a failure for a refund that
// had already been applied.
interface RefundWire {
  paymentId: string;
  invoiceId: string;
  refundedAmount: MoneyWire;
  remainingRefundable: MoneyWire;
  paymentStatus: PaymentStatus;
  invoiceStatus: InvoiceStatus;
  message: string;
}

/** Domain result of billingApi.refundPayment (currency units). */
export interface RefundResult {
  invoice: Invoice;
  paymentId: string;
  refundedAmount: number;
  remainingRefundable: number;
  paymentStatus: PaymentStatus;
  invoiceStatus: InvoiceStatus;
  message: string;
}

interface InvoiceWire {
  id: string;
  patientId: string;
  patientName: string;
  patientEmail?: string | null;
  patientPhone?: string | null;
  invoiceNumber: string;
  status: InvoiceStatus;
  lineItems: LineItemWire[];
  taxRate: MoneyWire;
  dueDate?: string | null;
  notes?: string | null;
  subtotal: MoneyWire;
  tax: MoneyWire;
  total: MoneyWire;
  createdAt: string;
  updatedAt: string;
  amountPaid: MoneyWire;
  balanceDue: MoneyWire;
  payments?: PaymentWire[];
}

interface InvoiceListWire {
  invoices: InvoiceWire[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  nextOffset?: number | null;
}

interface BillingSummaryWire {
  totalInvoices: number;
  totalRevenue: MoneyWire;
  totalTax: MoneyWire;
  totalPayments: number;
  totalCollected: MoneyWire;
  outstandingBalance: MoneyWire;
  statusBreakdown: Array<{
    status: InvoiceStatus;
    count: number;
    amount: MoneyWire;
  }>;
}

function parseMoney(value: MoneyWire, field: string): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid billing amount for ${field}`);
  }
  return parsed;
}

function toCents(value: number): number {
  // Misnomer kept for backward compatibility: normalizes to whole cents as a
  // currency-unit amount (the API accepts dollars with 2-decimal precision).
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function mapPayment(payment: PaymentWire): InvoicePayment {
  return {
    id: payment.id,
    invoiceId: payment.invoiceId,
    patientId: payment.patientId,
    date: payment.createdAt.slice(0, 10),
    method: payment.paymentMethod,
    reference: payment.transactionId || undefined,
    amount: parseMoney(payment.amount, 'payment.amount'),
    refundedAmount: parseMoney(payment.refundedAmount, 'payment.refundedAmount'),
    status: payment.status,
    notes: payment.notes || undefined,
  };
}

function mapInvoice(invoice: InvoiceWire): Invoice {
  return {
    id: invoice.id,
    patientId: invoice.patientId,
    patientName: invoice.patientName,
    patientEmail: invoice.patientEmail || undefined,
    patientPhone: invoice.patientPhone || undefined,
    invoiceNumber: invoice.invoiceNumber,
    status: invoice.status,
    lineItems: invoice.lineItems.map((item): InvoiceLineItem => ({
      description: item.description,
      quantity: item.quantity,
      unitPrice: parseMoney(item.unitPrice, 'lineItem.unitPrice'),
      total: parseMoney(item.total, 'lineItem.total'),
    })),
    subtotal: parseMoney(invoice.subtotal, 'invoice.subtotal'),
    taxRate: parseMoney(invoice.taxRate, 'invoice.taxRate') * 100,
    taxAmount: parseMoney(invoice.tax, 'invoice.tax'),
    total: parseMoney(invoice.total, 'invoice.total'),
    amountPaid: parseMoney(invoice.amountPaid, 'invoice.amountPaid'),
    balance: parseMoney(invoice.balanceDue, 'invoice.balanceDue'),
    issueDate: invoice.createdAt.slice(0, 10),
    dueDate: invoice.dueDate || undefined,
    notes: invoice.notes || undefined,
    payments: (invoice.payments ?? []).map(mapPayment),
    createdAt: invoice.createdAt,
    updatedAt: invoice.updatedAt,
  };
}

function mapSummary(summary: BillingSummaryWire): BillingSummary {
  const statusBreakdown: BillingStatusBreakdown[] = summary.statusBreakdown.map(item => ({
    status: item.status,
    count: item.count,
    amount: parseMoney(item.amount, `summary.${item.status}.amount`),
  }));
  const pending = statusBreakdown.find(item => item.status === 'pending');
  const overdue = statusBreakdown.find(item => item.status === 'overdue');

  return {
    totalInvoices: summary.totalInvoices,
    totalRevenue: parseMoney(summary.totalRevenue, 'summary.totalRevenue'),
    totalTax: parseMoney(summary.totalTax, 'summary.totalTax'),
    totalPayments: summary.totalPayments,
    totalCollected: parseMoney(summary.totalCollected, 'summary.totalCollected'),
    outstandingBalance: parseMoney(summary.outstandingBalance, 'summary.outstandingBalance'),
    statusBreakdown,
    pendingCount: pending?.count ?? 0,
    pendingAmount: pending?.amount ?? 0,
    overdueCount: overdue?.count ?? 0,
  };
}

export const billingApi = {
  async getInvoices(filters?: {
    status?: InvoiceStatus;
    patientId?: string;
    limit?: number;
    offset?: number;
  }): Promise<Invoice[]> {
    const params: Record<string, unknown> = {};
    if (filters?.status) params.status = filters.status;
    if (filters?.patientId) params.patient_id = filters.patientId;
    if (filters?.limit) params.limit = filters.limit;
    if (filters?.offset) params.offset = filters.offset;

    const response = await apiClient.get<InvoiceListWire | InvoiceWire[]>(
      '/billing/invoices/',
      params,
    );
    const data = requireApiData(response, 'Failed to load invoices');
    const invoices = Array.isArray(data) ? data : data.invoices;
    return invoices.map(mapInvoice);
  },

  async getInvoice(invoiceId: string): Promise<Invoice> {
    const invoice = requireApiData(
      await apiClient.get<InvoiceWire>(`/billing/invoices/${invoiceId}`),
      'Failed to load invoice',
    );
    return mapInvoice(invoice);
  },

  async getSummary(): Promise<BillingSummary> {
    const summary = requireApiData(
      await apiClient.get<BillingSummaryWire>('/billing/summary'),
      'Failed to load billing summary',
    );
    return mapSummary(summary);
  },

  async createInvoice(data: {
    patientId: string;
    lineItems: Array<Pick<InvoiceLineItem, 'description' | 'quantity' | 'unitPrice'>>;
    taxRatePercent?: number;
    dueDate?: string;
    notes?: string;
  }): Promise<Invoice> {
    if (data.lineItems.length === 0) {
      throw new Error('An invoice requires at least one line item');
    }

    const payload: Record<string, unknown> = {
      patient_id: data.patientId,
      due_date: data.dueDate || undefined,
      notes: data.notes,
      line_items: data.lineItems.map(item => ({
        description: item.description,
        quantity: item.quantity,
        unit_price: toCents(item.unitPrice),
        total: toCents(item.quantity * item.unitPrice),
      })),
    };
    if (data.taxRatePercent !== undefined) {
      payload.tax_rate = data.taxRatePercent / 100;
    }

    const invoice = requireApiData(
      await apiClient.post<InvoiceWire>('/billing/invoices/', payload),
      'Failed to create invoice',
    );
    return mapInvoice(invoice);
  },

  async updateStatus(invoiceId: string, status: InvoiceStatus): Promise<Invoice> {
    const invoice = requireApiData(
      await apiClient.put<InvoiceWire>(`/billing/invoices/${invoiceId}`, { status }),
      'Failed to update invoice status',
    );
    return mapInvoice(invoice);
  },

  async recordPayment(invoiceId: string, payment: {
    amount: number;
    method: PaymentMethod;
    patientId?: string;
    reference: string;
    notes?: string;
  }): Promise<RecordPaymentResult> {
    const existingInvoice = payment.patientId
      ? null
      : await billingApi.getInvoice(invoiceId);
    const patientId = payment.patientId ?? existingInvoice?.patientId;
    if (!patientId) {
      throw new Error('Invoice patient is required to record a payment');
    }

    const paymentWire = requireApiData(
      await apiClient.post<PaymentWire>('/billing/payments/', {
        invoice_id: invoiceId,
        patient_id: patientId,
        amount: toCents(payment.amount),
        payment_method: payment.method,
        transaction_id: payment.reference,
        notes: payment.notes,
      }),
      'Failed to record payment',
    );
    const invoice = await billingApi.getInvoice(invoiceId);
    return { invoice, payment: mapPayment(paymentWire) };
  },

  async cancelInvoice(invoiceId: string): Promise<void> {
    requireApiSuccess(
      await apiClient.delete<{ message: string }>(`/billing/invoices/${invoiceId}`),
      'Failed to cancel invoice',
    );
  },

  /**
   * Refund all or part of a recorded payment (2026-09 production gap).
   * Server endpoint: POST /billing/payments/{paymentId}/refund
   * Mirrors recordPayment: currency units on the wire, invoice refreshed after.
   */
  async refundPayment(paymentId: string, refund: {
    amount: number;
    reason?: string;
  }): Promise<RefundResult> {
    const wire = requireApiData(
      await apiClient.post<RefundWire>(`/billing/payments/${paymentId}/refund`, {
        amount: toCents(refund.amount),
        reason: refund.reason,
      }),
      'Failed to refund payment',
    );
    const invoice = await billingApi.getInvoice(wire.invoiceId);
    return {
      invoice,
      paymentId: wire.paymentId,
      refundedAmount: parseMoney(wire.refundedAmount, 'refund.refundedAmount'),
      remainingRefundable: parseMoney(wire.remainingRefundable, 'refund.remainingRefundable'),
      paymentStatus: wire.paymentStatus,
      invoiceStatus: wire.invoiceStatus,
      message: wire.message,
    };
  },

  generateReceiptHTML(invoice: Invoice, currency: string = 'USD'): string {
    const escapeHtml = (value: unknown): string =>
      String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const formatMoney = (amount: number) => formatCurrency(amount, currency);
    const lineItemsHTML = invoice.lineItems.map(item => `
      <tr>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">${escapeHtml(item.description)}</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">${escapeHtml(item.quantity)}</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${escapeHtml(formatMoney(item.unitPrice))}</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${escapeHtml(formatMoney(item.total))}</td>
      </tr>
    `).join('');

    const paymentsHTML = invoice.payments.map(payment => `
      <tr>
        <td style="padding: 8px;">${escapeHtml(payment.date)}</td>
        <td style="padding: 8px;">${escapeHtml(payment.method.replace('_', ' '))}</td>
        <td style="padding: 8px;">${escapeHtml(payment.reference || '-')}</td>
        <td style="padding: 8px; text-align: right;">${escapeHtml(formatMoney(payment.amount - payment.refundedAmount))}</td>
      </tr>
    `).join('');

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Receipt - ${escapeHtml(invoice.invoiceNumber)}</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
          .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }
          .invoice-info { display: flex; justify-content: space-between; margin-bottom: 30px; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
          th { background: #f5f5f5; padding: 10px; text-align: left; }
          .totals { text-align: right; }
          .totals td { padding: 5px 0; }
          .total-row { font-weight: bold; font-size: 1.1em; }
          .paid-stamp { color: green; font-size: 1.5em; font-weight: bold; text-align: center; margin: 20px 0; }
          @media print { body { padding: 0; } }
        </style>
      </head>
      <body>
        <div class="header"><h1>Invoice Receipt</h1></div>
        <div class="invoice-info">
          <div>
            <h3>Bill To:</h3>
            <p><strong>${escapeHtml(invoice.patientName)}</strong><br>
            ${escapeHtml(invoice.patientEmail || '')}<br>
            ${escapeHtml(invoice.patientPhone || '')}</p>
          </div>
          <div style="text-align: right;">
            <h3>Invoice #${escapeHtml(invoice.invoiceNumber)}</h3>
            <p>Issue Date: ${escapeHtml(invoice.issueDate)}<br>
            Due Date: ${escapeHtml(invoice.dueDate || 'Not set')}</p>
          </div>
        </div>
        <table>
          <thead><tr><th>Description</th><th style="text-align: center;">Qty</th><th style="text-align: right;">Price</th><th style="text-align: right;">Total</th></tr></thead>
          <tbody>${lineItemsHTML}</tbody>
        </table>
        <table class="totals" style="width: 300px; margin-left: auto;">
          <tr><td>Subtotal:</td><td>${escapeHtml(formatMoney(invoice.subtotal))}</td></tr>
          ${invoice.taxAmount > 0 ? `<tr><td>Tax (${escapeHtml(invoice.taxRate)}%):</td><td>${escapeHtml(formatMoney(invoice.taxAmount))}</td></tr>` : ''}
          <tr class="total-row" style="border-top: 2px solid #333;"><td>Total:</td><td>${escapeHtml(formatMoney(invoice.total))}</td></tr>
          <tr><td>Amount Paid:</td><td>${escapeHtml(formatMoney(invoice.amountPaid))}</td></tr>
          <tr class="total-row"><td>Balance Due:</td><td>${escapeHtml(formatMoney(invoice.balance))}</td></tr>
        </table>
        ${invoice.status === 'paid' ? '<div class="paid-stamp">PAID IN FULL</div>' : ''}
        ${invoice.payments.length > 0 ? `
          <h3>Payment History</h3>
          <table>
            <thead><tr><th>Date</th><th>Method</th><th>Reference</th><th style="text-align: right;">Net Amount</th></tr></thead>
            <tbody>${paymentsHTML}</tbody>
          </table>
        ` : ''}
        <p style="margin-top: 40px; text-align: center; color: #666;">Thank you for your visit.</p>
      </body>
      </html>
    `;
  },
};
