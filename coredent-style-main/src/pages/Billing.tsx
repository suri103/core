// ============================================
// CoreDent PMS - Billing Page
// Invoice management and payment tracking
// ============================================

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Plus,
  Search,
  FileText,
  DollarSign,
  AlertTriangle,
  TrendingUp
} from 'lucide-react';
import { InvoiceCard } from '@/components/billing/InvoiceCard';
import { CreateInvoiceDialog } from '@/components/billing/CreateInvoiceDialog';
import { RecordPaymentDialog } from '@/components/billing/RecordPaymentDialog';
import { RefundPaymentDialog } from '@/components/billing/RefundPaymentDialog';
import { InvoiceDetails } from '@/components/billing/InvoiceDetails';
import { billingApi } from '@/services/billingApi';
import { useAuth } from '@/contexts/auth-context';
import { settingsApi } from '@/services/api';
import { triggerAutomation } from '@/services/automationApi';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import { logger } from '@/lib/logger';
import type { Invoice, InvoicePayment, PaymentMethod } from '@/types/billing';

type TabFilter = 'all' | 'pending' | 'paid' | 'overdue';

export default function Billing() {
  const { toast } = useToast();
  const { user } = useAuth();
  const clinicName = user?.practiceName?.trim() || 'Your dental clinic';
  const queryClient = useQueryClient();
  
  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<TabFilter>('all');
  
  // Dialog states
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [paymentInvoice, setPaymentInvoice] = useState<Invoice | null>(null);
  const [viewingInvoice, setViewingInvoice] = useState<Invoice | null>(null);
  const [deletingInvoice, setDeletingInvoice] = useState<Invoice | null>(null);
  const [refundTarget, setRefundTarget] = useState<{
    invoice: Invoice;
    payment: InvoicePayment;
  } | null>(null);

  // Load invoices with React Query
  const { data: invoices = [], isLoading: isLoadingInvoices, isError: invoicesError } = useQuery({
    queryKey: ['billing', 'invoices'],
    queryFn: () => billingApi.getInvoices(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  // Load billing summary
  const { data: summary, isLoading: isLoadingSummary, isError: summaryError } = useQuery({
    queryKey: ['billing', 'summary'],
    queryFn: () => billingApi.getSummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Load persisted billing preferences for exact tax, terms, and payment methods.
  // The backend remains authoritative if this owner/admin settings request is unavailable.
  const { data: preferencesResponse } = useQuery({
    queryKey: ['settings', 'billing-preferences'],
    queryFn: () => settingsApi.getBillingPreferences(),
    staleTime: 5 * 60 * 1000,
  });
  const billingPreferences = preferencesResponse?.success
    ? preferencesResponse.data
    : undefined;

  const isLoading = isLoadingInvoices || isLoadingSummary;

  const { currency, formatCurrency } = useCurrencyFormatter();

  // Filter invoices
  const filteredInvoices = invoices.filter(invoice => {
    // Search filter
    const matchesSearch = 
      invoice.invoiceNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      invoice.patientName.toLowerCase().includes(searchQuery.toLowerCase());
    
    // Tab filter
    let matchesTab = true;
    if (activeTab === 'pending') {
      matchesTab = ['draft', 'pending', 'partially_paid'].includes(invoice.status);
    } else if (activeTab === 'paid') {
      matchesTab = invoice.status === 'paid';
    } else if (activeTab === 'overdue') {
      matchesTab = invoice.status === 'overdue';
    }
    
    return matchesSearch && matchesTab;
  });

  // Create invoice. Returns true on success so the dialog can dismiss;
  // false tells it to keep the form state for retry.
  const handleCreateInvoice = async (data: {
    patientId: string;
    patientName: string;
    patientEmail?: string;
    patientPhone?: string;
    lineItems: {
      description: string;
      quantity: number;
      unitPrice: number;
    }[];
    taxRatePercent?: number;
    dueDate: string;
    notes?: string;
  }): Promise<boolean> => {
    try {
      const newInvoice = await billingApi.createInvoice(data);
      queryClient.invalidateQueries({ queryKey: ['billing'] });

      toast({
        title: 'Invoice created',
        description: `Invoice ${newInvoice.invoiceNumber} has been created`,
      });

      // Trigger invoice_created automation
      Promise.resolve(triggerAutomation('invoice_created', {
        paymentId: '',
        invoiceId: newInvoice.id,
        patientName: data.patientName,
        patientEmail: data.patientEmail,
        amount: newInvoice.total,
        paymentMethod: '',
        clinicName,
      })).catch((automationError) => {
        logger.warn('invoice_created automation failed', {
          error: automationError instanceof Error ? automationError.message : String(automationError),
        });
      });

      return true;
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to create invoice. The dialog has been kept open so you can retry.',
        variant: 'destructive',
      });
      return false;
    }
  };

  // Record payment. Returns true on success so the dialog can dismiss.
  const handleRecordPayment = async (data: {
    amount: number;
    method: PaymentMethod;
    reference: string;
    notes?: string;
  }): Promise<boolean> => {
    if (!paymentInvoice) return false;
    
    try {
      const result = await billingApi.recordPayment(paymentInvoice.id, data);
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      if (viewingInvoice?.id === result.invoice.id) {
        setViewingInvoice(result.invoice);
      }
      
      toast({
        title: 'Payment recorded',
        description: `${formatCurrency(data.amount)} payment recorded`,
      });

      // Trigger payment_received automation
      Promise.resolve(triggerAutomation('payment_received', {
        paymentId: result.payment.id,
        invoiceId: paymentInvoice.id,
        patientName: paymentInvoice.patientName,
        patientEmail: paymentInvoice.patientEmail,
        amount: data.amount,
        paymentMethod: data.method,
        clinicName,
      })).catch((automationError) => {
        logger.warn('payment_received automation failed', {
          error: automationError instanceof Error ? automationError.message : String(automationError),
        });
      });

      return true;
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to record payment. The dialog has been kept open so you can retry.',
        variant: 'destructive',
      });
      return false;
    }
  };

  // Refund a recorded payment. Returns true on success so the dialog can dismiss.
  const handleRefund = async (data: {
    paymentId: string;
    amount: number;
    reason?: string;
  }): Promise<boolean> => {
    try {
      const result = await billingApi.refundPayment(data.paymentId, {
        amount: data.amount,
        reason: data.reason,
      });
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      if (viewingInvoice?.id === result.invoice.id) {
        setViewingInvoice(result.invoice);
      }

      toast({
        title: 'Payment refunded',
        description: `${formatCurrency(data.amount)} refunded`,
      });

      // Trigger payment_refunded automation (best-effort, like payments).
      Promise.resolve(triggerAutomation('payment_refunded', {
        paymentId: data.paymentId,
        invoiceId: result.invoice.id,
        patientName: result.invoice.patientName,
        patientEmail: result.invoice.patientEmail,
        amount: data.amount,
        clinicName,
      })).catch((automationError) => {
        logger.warn('payment_refunded automation failed', {
          error: automationError instanceof Error ? automationError.message : String(automationError),
        });
      });

      return true;
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to refund payment. The dialog has been kept open so you can retry.',
        variant: 'destructive',
      });
      return false;
    }
  };

  // Download receipt
  const handleDownload = (invoice: Invoice) => {
    const html = billingApi.generateReceiptHTML(invoice, currency);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `receipt-${invoice.invoiceNumber}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    toast({
      title: 'Receipt downloaded',
      description: 'Open the file in a browser to print',
    });
  };

  // Send invoice
  const handleSend = async (invoice: Invoice) => {
    try {
      await billingApi.updateStatus(invoice.id, 'pending');
      queryClient.invalidateQueries({ queryKey: ['billing'] });

      toast({
        title: 'Invoice issued',
        description: 'Invoice status updated to Pending',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to update invoice status',
        variant: 'destructive',
      });
    }
  };

  // Cancel invoice (the backend performs a terminal soft cancellation).
  const handleCancel = async () => {
    if (!deletingInvoice) return;

    try {
      await billingApi.cancelInvoice(deletingInvoice.id);
      queryClient.invalidateQueries({ queryKey: ['billing'] });
      if (viewingInvoice?.id === deletingInvoice.id) {
        setViewingInvoice(null);
      }
      
      setDeletingInvoice(null);
      toast({
        title: 'Invoice cancelled',
        description: 'Invoice has been cancelled',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to cancel invoice',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Billing</h1>
          <p className="text-muted-foreground">
            Manage invoices and track payments
          </p>
        </div>
        
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Invoice
        </Button>
      </div>

      {(invoicesError || summaryError) && (
        <Alert variant="destructive" role="alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Billing data unavailable</AlertTitle>
          <AlertDescription>
            Invoices or billing totals could not be loaded. No zero-value estimates are being substituted.
          </AlertDescription>
        </Alert>
      )}

      {/* Summary cards */}
      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
                  <DollarSign className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Outstanding (90-day invoices)</p>
                  <p className="text-xl font-bold">{formatCurrency(summary.outstandingBalance)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Collected (90 days)</p>
                  <p className="text-xl font-bold">{formatCurrency(summary.totalCollected)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
                  <FileText className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Pending</p>
                  <p className="text-xl font-bold">{summary.pendingCount}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Overdue</p>
                  <p className="text-xl font-bold">{summary.overdueCount}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search and filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search invoices..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabFilter)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="pending">Pending</TabsTrigger>
            <TabsTrigger value="paid">Paid</TabsTrigger>
            <TabsTrigger value="overdue">Overdue</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Invoice grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-[200px] rounded-xl" />
          ))}
        </div>
      ) : filteredInvoices.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No invoices found</h3>
          <p className="text-muted-foreground mt-1">
            {searchQuery
              ? 'Try adjusting your search terms'
              : 'Create a new invoice to get started'}
          </p>
          {!searchQuery && (
            <Button className="mt-4" onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Invoice
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredInvoices.map(invoice => (
            <InvoiceCard
              key={invoice.id}
              invoice={invoice}
              onView={setViewingInvoice}
              onRecordPayment={setPaymentInvoice}
              onDownload={handleDownload}
              onSend={handleSend}
              onDelete={setDeletingInvoice}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <CreateInvoiceDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onSubmit={handleCreateInvoice}
        taxRatePercent={billingPreferences?.taxRate}
        paymentTermsDays={billingPreferences?.paymentTerms}
      />

      <RecordPaymentDialog
        open={!!paymentInvoice}
        onOpenChange={(open) => !open && setPaymentInvoice(null)}
        invoice={paymentInvoice}
        acceptedPaymentMethods={billingPreferences?.acceptedPaymentMethods}
        onSubmit={handleRecordPayment}
      />

      <InvoiceDetails
        open={!!viewingInvoice}
        onOpenChange={(open) => !open && setViewingInvoice(null)}
        invoice={viewingInvoice}
        onRecordPayment={() => {
          setPaymentInvoice(viewingInvoice);
        }}
        onDownload={() => viewingInvoice && handleDownload(viewingInvoice)}
        onSend={() => viewingInvoice && handleSend(viewingInvoice)}
        onRefund={(payment) => {
          if (!viewingInvoice) return;
          setRefundTarget({ invoice: viewingInvoice, payment });
        }}
      />

      <RefundPaymentDialog
        open={!!refundTarget}
        onOpenChange={(open) => !open && setRefundTarget(null)}
        invoice={refundTarget?.invoice ?? null}
        payment={refundTarget?.payment ?? null}
        onSubmit={handleRefund}
      />

      <AlertDialog open={!!deletingInvoice} onOpenChange={(open) => !open && setDeletingInvoice(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Invoice?</AlertDialogTitle>
            <AlertDialogDescription>
              Invoice {deletingInvoice?.invoiceNumber} will be marked cancelled. Invoices with recorded payments must be refunded before cancellation.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Invoice</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancel}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Cancel Invoice
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
