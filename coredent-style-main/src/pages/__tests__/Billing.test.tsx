import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  getInvoices: vi.fn(),
  getSummary: vi.fn(),
  createInvoice: vi.fn(),
  recordPayment: vi.fn(),
  updateStatus: vi.fn(),
  cancelInvoice: vi.fn(),
  getBillingPreferences: vi.fn(),
  generateReceiptHTML: vi.fn(),
  triggerAutomation: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/services/billingApi", () => ({
  billingApi: {
    getInvoices: mocks.getInvoices,
    getSummary: mocks.getSummary,
    createInvoice: mocks.createInvoice,
    recordPayment: mocks.recordPayment,
    updateStatus: mocks.updateStatus,
    cancelInvoice: mocks.cancelInvoice,
    generateReceiptHTML: mocks.generateReceiptHTML,
  },
}));

vi.mock("@/services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/api")>();
  return {
    ...actual,
    settingsApi: {
      ...actual.settingsApi,
      getBillingPreferences: mocks.getBillingPreferences,
    },
  };
});

vi.mock("@/services/automationApi", () => ({
  triggerAutomation: mocks.triggerAutomation,
}));

vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ open, children }: any) => (open ? <div data-testid="billing-delete-dialog">{children}</div> : null),
  AlertDialogAction: ({ children, ...props }: any) => <button {...props}>{children}</button>,
  AlertDialogCancel: ({ children, ...props }: any) => <button {...props}>{children}</button>,
  AlertDialogContent: ({ children }: any) => <div>{children}</div>,
  AlertDialogDescription: ({ children }: any) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: any) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: any) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: any) => <h2>{children}</h2>,
}));

vi.mock("@/components/billing/InvoiceCard", () => ({
  InvoiceCard: ({ invoice, onView, onRecordPayment, onDownload, onSend, onDelete }: any) => (
    <div data-testid={`invoice-card-${invoice.id}`}>
      <span>{invoice.invoiceNumber}</span>
      <button onClick={() => onView(invoice)}>View</button>
      <button onClick={() => onRecordPayment(invoice)}>Record Payment</button>
      <button onClick={() => onDownload(invoice)}>Download</button>
      <button onClick={() => onSend(invoice)}>Send</button>
      <button onClick={() => onDelete(invoice)}>Cancel Invoice</button>
    </div>
  ),
}));

vi.mock("@/components/billing/CreateInvoiceDialog", () => ({
  CreateInvoiceDialog: ({ open, onSubmit }: any) =>
    open ? (
      <div data-testid="create-invoice-dialog">
        <button
          onClick={() =>
            onSubmit({
              patientId: "patient-3",
              patientName: "Ada Lovelace",
              patientEmail: "ada@example.com",
              patientPhone: "555-0100",
              lineItems: [
                {
                  description: "Adult cleaning",
                  quantity: 1,
                  unitPrice: 125,
                },
              ],
              dueDate: "2026-07-15",
              notes: "Created from test",
            })
          }
        >
          Submit Invoice
        </button>
      </div>
    ) : null,
}));

vi.mock("@/components/billing/RecordPaymentDialog", () => ({
  RecordPaymentDialog: ({ open, onSubmit }: any) =>
    open ? (
      <div data-testid="record-payment-dialog">
        <button
          onClick={() =>
            onSubmit({
              amount: 50,
              method: "cash",
              reference: "REC-1",
              notes: "Paid in test",
            })
          }
        >
          Submit Payment
        </button>
      </div>
    ) : null,
}));

vi.mock("@/components/billing/InvoiceDetails", () => ({
  InvoiceDetails: ({ open, invoice, onRecordPayment, onDownload, onSend }: any) =>
    open ? (
      <div data-testid="invoice-details">
        <p>{invoice?.invoiceNumber}</p>
        <button onClick={onRecordPayment}>Record from details</button>
        <button onClick={onDownload}>Download from details</button>
        <button onClick={onSend}>Send from details</button>
      </div>
    ) : null,
}));

import Billing from "../Billing";

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

const invoices = [
  {
    id: "inv-1",
    patientId: "p-1",
    patientName: "Alice Adams",
    patientEmail: "alice@example.com",
    patientPhone: "555-1111",
    invoiceNumber: "INV-001",
    status: "draft",
    lineItems: [],
    subtotal: 100,
    taxRate: 0,
    taxAmount: 0,
    total: 100,
    amountPaid: 0,
    balance: 100,
    issueDate: "2026-06-01",
    dueDate: "2026-06-15",
    payments: [],
    createdAt: "2026-06-01T00:00:00.000Z",
    updatedAt: "2026-06-01T00:00:00.000Z",
  },
  {
    id: "inv-2",
    patientId: "p-2",
    patientName: "Bob Brown",
    patientEmail: "bob@example.com",
    invoiceNumber: "INV-002",
    status: "paid",
    lineItems: [],
    subtotal: 200,
    taxRate: 0,
    taxAmount: 0,
    total: 200,
    amountPaid: 200,
    balance: 0,
    issueDate: "2026-06-02",
    dueDate: "2026-06-16",
    payments: [],
    createdAt: "2026-06-02T00:00:00.000Z",
    updatedAt: "2026-06-02T00:00:00.000Z",
  },
  {
    id: "inv-3",
    patientId: "p-3",
    patientName: "Charlie Clark",
    invoiceNumber: "INV-003",
    status: "overdue",
    lineItems: [],
    subtotal: 300,
    taxRate: 0,
    taxAmount: 0,
    total: 300,
    amountPaid: 0,
    balance: 300,
    issueDate: "2026-05-01",
    dueDate: "2026-05-15",
    payments: [],
    createdAt: "2026-05-01T00:00:00.000Z",
    updatedAt: "2026-05-01T00:00:00.000Z",
  },
];

const summary = {
  totalInvoices: 3,
  totalRevenue: 600,
  totalTax: 0,
  totalPayments: 1,
  totalCollected: 200,
  outstandingBalance: 400,
  statusBreakdown: [
    { status: 'pending', count: 1, amount: 100 },
    { status: 'overdue', count: 1, amount: 300 },
  ],
  overdueCount: 1,
  pendingCount: 1,
  pendingAmount: 100,
};

describe("Billing Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getInvoices.mockResolvedValue(invoices);
    mocks.getSummary.mockResolvedValue(summary);
    mocks.createInvoice.mockResolvedValue({ ...invoices[0], id: "inv-new", invoiceNumber: "INV-999", total: 125 });
    mocks.recordPayment.mockResolvedValue({
      invoice: { ...invoices[0], status: 'partially_paid', amountPaid: 50, balance: 50 },
      payment: {
        id: 'pay-1',
        invoiceId: 'inv-1',
        patientId: 'p-1',
        date: '2026-06-10',
        method: 'cash',
        amount: 50,
        refundedAmount: 0,
        status: 'completed',
      },
    });
    mocks.updateStatus.mockResolvedValue({ ...invoices[0], status: "pending" });
    mocks.cancelInvoice.mockResolvedValue(undefined);
    mocks.getBillingPreferences.mockResolvedValue({
      success: true,
      data: {
        taxRate: 5,
        currency: 'USD',
        invoicePrefix: 'INV',
        paymentTerms: 30,
        lateFeePercentage: 0,
        acceptedPaymentMethods: ['cash', 'card', 'check'],
        autoSendInvoices: false,
        autoSendReminders: false,
        reminderDaysBefore: 3,
      },
    });
    mocks.generateReceiptHTML.mockReturnValue("<html><body>receipt</body></html>");

    if (typeof URL.createObjectURL !== "function") {
      Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock"), writable: true });
    }
    if (typeof URL.revokeObjectURL !== "function") {
      Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
    }
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  });

  it("renders invoices, filters them, and shows summary data", async () => {
    render(<Billing />, { wrapper: createWrapper() });

    await waitFor(() => expect(screen.getByText("INV-001")).toBeInTheDocument());
    expect(screen.getByText("INV-002")).toBeInTheDocument();
    expect(screen.getByText("INV-003")).toBeInTheDocument();
    expect(screen.getByText("$400.00")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/search invoices/i), "Bob");
    expect(screen.queryByText("INV-001")).toBeNull();
    expect(screen.getByText("INV-002")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /paid/i }));
    expect(screen.getByText("INV-002")).toBeInTheDocument();
    expect(screen.queryByText("INV-001")).toBeNull();
  });

  it("drives invoice actions end-to-end", async () => {
    const user = userEvent.setup();
    render(<Billing />, { wrapper: createWrapper() });

    await waitFor(() => expect(screen.getByText("INV-001")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /new invoice/i }));
    await user.click(screen.getByRole("button", { name: /submit invoice/i }));
    await waitFor(() => expect(mocks.createInvoice).toHaveBeenCalled());
    expect(mocks.triggerAutomation).toHaveBeenCalledWith(
      "invoice_created",
      expect.objectContaining({ invoiceId: "inv-new", patientName: "Ada Lovelace" }),
    );

    await user.click(within(screen.getByTestId("invoice-card-inv-1")).getByRole("button", { name: /view/i }));
    await waitFor(() => expect(screen.getByTestId("invoice-details")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /download from details/i }));
    expect(mocks.generateReceiptHTML).toHaveBeenCalledWith(expect.objectContaining({ invoiceNumber: "INV-001" }), "USD");
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /send from details/i }));
    await waitFor(() => expect(mocks.updateStatus).toHaveBeenCalledWith("inv-1", "pending"));

    await user.click(screen.getByRole("button", { name: /record from details/i }));
    await waitFor(() => expect(screen.getByTestId("record-payment-dialog")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /submit payment/i }));
    await waitFor(() => expect(mocks.recordPayment).toHaveBeenCalledWith("inv-1", expect.objectContaining({ amount: 50, method: "cash" })));
    expect(mocks.triggerAutomation).toHaveBeenCalledWith(
      "payment_received",
      expect.objectContaining({ invoiceId: "inv-1", patientName: "Alice Adams", amount: 50 }),
    );

    await user.click(within(screen.getByTestId("invoice-card-inv-1")).getByRole("button", { name: /cancel invoice/i }));
    await waitFor(() => expect(screen.getByTestId("billing-delete-dialog")).toBeInTheDocument());
    await user.click(within(screen.getByTestId("billing-delete-dialog")).getByRole("button", { name: /^cancel invoice$/i }));
    await waitFor(() => expect(mocks.cancelInvoice).toHaveBeenCalledWith("inv-1"));
  });
});
