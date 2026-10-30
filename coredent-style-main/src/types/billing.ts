// ============================================
// CoreDent PMS - Billing Types
// Canonical frontend view models mapped from the backend billing contract.
// ============================================

export type InvoiceStatus =
  | 'draft'
  | 'pending'
  | 'paid'
  | 'partially_paid'
  | 'overdue'
  | 'cancelled';

export type PaymentMethod = 'cash' | 'card' | 'check' | 'insurance' | 'upi' | 'other';
export type PaymentStatus = 'completed' | 'pending' | 'failed' | 'refunded' | 'partially_refunded';

export interface InvoiceLineItem {
  description: string;
  quantity: number;
  unitPrice: number;
  total: number;
}

export interface InvoicePayment {
  id: string;
  invoiceId: string;
  patientId: string;
  date: string;
  method: PaymentMethod;
  reference?: string;
  amount: number;
  refundedAmount: number;
  status: PaymentStatus;
  notes?: string;
}

export interface Invoice {
  id: string;
  patientId: string;
  patientName: string;
  patientEmail?: string;
  patientPhone?: string;
  invoiceNumber: string;
  status: InvoiceStatus;
  lineItems: InvoiceLineItem[];
  subtotal: number;
  /** Percentage for display (for example, 5 means 5%). */
  taxRate: number;
  taxAmount: number;
  total: number;
  amountPaid: number;
  balance: number;
  /** Calendar date derived from the backend created_at timestamp. */
  issueDate: string;
  dueDate?: string;
  notes?: string;
  payments: InvoicePayment[];
  createdAt: string;
  updatedAt: string;
}

export interface BillingStatusBreakdown {
  status: InvoiceStatus;
  count: number;
  amount: number;
}

export interface BillingSummary {
  totalInvoices: number;
  totalRevenue: number;
  totalTax: number;
  totalPayments: number;
  totalCollected: number;
  outstandingBalance: number;
  statusBreakdown: BillingStatusBreakdown[];
  pendingCount: number;
  pendingAmount: number;
  overdueCount: number;
}

export interface RecordPaymentResult {
  invoice: Invoice;
  payment: InvoicePayment;
}
