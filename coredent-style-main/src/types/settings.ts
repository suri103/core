// ============================================
// CoreDent PMS - Settings Types
// Exact frontend representation of the persisted billing preferences.
// ============================================

export type PaymentMethod = 'cash' | 'card' | 'check' | 'insurance' | 'upi' | 'other';

export interface BillingPreferences {
  /** Percentage, from 0 through 100. */
  taxRate: number;
  currency: string;
  invoicePrefix: string;
  paymentTerms: number;
  lateFeePercentage: number;
  acceptedPaymentMethods: PaymentMethod[];
  autoSendInvoices: boolean;
  autoSendReminders: boolean;
  reminderDaysBefore: number;
}

export const paymentMethodLabels: Record<PaymentMethod, string> = {
  cash: 'Cash',
  card: 'Card',
  check: 'Check',
  insurance: 'Insurance',
  upi: 'UPI',
  other: 'Other',
};

export const defaultBillingPreferences: BillingPreferences = {
  taxRate: 0,
  currency: 'USD',
  invoicePrefix: 'INV',
  paymentTerms: 30,
  lateFeePercentage: 0,
  acceptedPaymentMethods: ['cash', 'card', 'check'],
  autoSendInvoices: false,
  autoSendReminders: false,
  reminderDaysBefore: 3,
};

export const currencyOptions = [
  { code: 'USD', label: 'US Dollar ($)', symbol: '$' },
  { code: 'EUR', label: 'Euro (€)', symbol: '€' },
  { code: 'GBP', label: 'British Pound (£)', symbol: '£' },
  { code: 'CAD', label: 'Canadian Dollar ($)', symbol: '$' },
  { code: 'AUD', label: 'Australian Dollar ($)', symbol: '$' },
];
