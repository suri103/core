import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  FileText, 
  DollarSign, 
  Download, 
  Send, 
  Calendar, 
  User, 
  Mail, 
  Phone,
  Receipt,
  History
} from 'lucide-react';
import type { Invoice, InvoicePayment } from '@/types/billing';

interface InvoiceDetailsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoice: Invoice | null;
  onRecordPayment: () => void;
  onDownload: () => void;
  onSend: () => void;
  onRefund: (payment: InvoicePayment) => void;
}

export function InvoiceDetails({
  open,
  onOpenChange,
  invoice,
  onRecordPayment,
  onDownload,
  onSend,
  onRefund,
}: InvoiceDetailsProps) {
  const { formatCurrency } = useCurrencyFormatter();

  if (!invoice) return null;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20';
      case 'partially_paid':
        return 'bg-sky-500/10 text-sky-500 hover:bg-sky-500/20 border-sky-500/20';
      case 'pending':
        return 'bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20';
      case 'overdue':
        return 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20';
      case 'cancelled':
        return 'bg-neutral-500/10 text-neutral-500 hover:bg-neutral-500/20 border-neutral-500/20';
      default:
        return 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20'; // draft
    }
  };

  const isDraft = invoice.status === 'draft';
  const isPayable = ['pending', 'partially_paid', 'overdue'].includes(invoice.status);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto bg-card/95 border-l border-border backdrop-blur-md text-foreground flex flex-col justify-between">
        <div className="space-y-6">
          <SheetHeader className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm tracking-wide text-muted-foreground font-semibold">
                {invoice.invoiceNumber}
              </span>
              <Badge variant="outline" className={`${getStatusColor(invoice.status)} capitalize border px-2.5 py-0.5`}>
                {invoice.status.replace('_', ' ')}
              </Badge>
            </div>
            <SheetTitle className="text-2xl font-bold flex items-center gap-2">
              <Receipt className="h-6 w-6 text-primary" />
              Invoice Details
            </SheetTitle>
            <SheetDescription className="text-muted-foreground">
              Review invoice items, pricing details, and history.
            </SheetDescription>
          </SheetHeader>

          <Separator className="bg-border" />

          {/* Patient Details */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <User className="h-4 w-4 text-muted-foreground" />
              Patient Information
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-xl border border-border/60 bg-accent/15 p-4 text-sm">
              <div className="space-y-1">
                <span className="block text-xs text-muted-foreground uppercase tracking-wider">Patient Name</span>
                <span className="font-semibold text-foreground">{invoice.patientName}</span>
              </div>
              <div className="space-y-1 sm:text-right">
                <span className="block text-xs text-muted-foreground uppercase tracking-wider">Dates</span>
                <div className="text-xs text-foreground space-y-0.5">
                  <div className="flex items-center sm:justify-end gap-1 text-muted-foreground">
                    <Calendar className="h-3 w-3" /> Issued: {invoice.issueDate}
                  </div>
                  <div className="flex items-center sm:justify-end gap-1 font-medium text-rose-500">
                    <Calendar className="h-3 w-3" /> Due: {invoice.dueDate || 'Not set'}
                  </div>
                </div>
              </div>

              {(invoice.patientEmail || invoice.patientPhone) && (
                <div className="col-span-1 sm:col-span-2 pt-2 border-t border-border/30 flex flex-col sm:flex-row gap-2 sm:gap-6 text-xs text-muted-foreground">
                  {invoice.patientEmail && (
                    <span className="flex items-center gap-1.5">
                      <Mail className="h-3.5 w-3.5 text-muted-foreground/75" /> {invoice.patientEmail}
                    </span>
                  )}
                  {invoice.patientPhone && (
                    <span className="flex items-center gap-1.5">
                      <Phone className="h-3.5 w-3.5 text-muted-foreground/75" /> {invoice.patientPhone}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Line Items Breakdown */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Procedure Breakdown
            </h4>
            <div className="rounded-xl border border-border overflow-hidden bg-background/50">
              <table className="w-full text-sm text-left border-collapse">
                <thead className="bg-accent/40 text-[10px] uppercase font-bold text-muted-foreground tracking-wider border-b border-border">
                  <tr>
                    <th className="py-2 px-3">Description</th>
                    <th className="py-2 px-3 text-center">Qty</th>
                    <th className="py-2 px-3 text-right">Price</th>
                    <th className="py-2 px-3 text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/55">
                  {invoice.lineItems.map((item) => (
                    <tr key={`${item.description}-${item.quantity}-${item.unitPrice}`} className="hover:bg-accent/15 transition-colors">
                      <td className="py-2.5 px-3">
                        <div className="text-xs text-foreground font-medium line-clamp-1">{item.description}</div>
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono text-xs">{item.quantity}</td>
                      <td className="py-2.5 px-3 text-right font-mono text-xs">
                        {formatCurrency(item.unitPrice)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold font-mono text-xs">
                        {formatCurrency(item.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Totals Breakdown */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {invoice.notes ? (
              <div className="rounded-xl border border-border p-3 bg-accent/5 space-y-1.5 text-xs">
                <span className="font-semibold text-foreground uppercase tracking-wider block text-[10px]">Invoice Memo</span>
                <p className="text-muted-foreground whitespace-pre-line leading-relaxed">{invoice.notes}</p>
              </div>
            ) : (
              <div className="hidden sm:block"></div>
            )}

            <div className="rounded-xl border border-border/80 bg-accent/10 p-4 space-y-2 text-xs">
              <div className="flex justify-between text-muted-foreground">
                <span>Subtotal:</span>
                <span className="font-mono">{formatCurrency(invoice.subtotal)}</span>
              </div>
              {invoice.taxAmount > 0 && (
                <div className="flex justify-between text-muted-foreground">
                  <span>Tax ({invoice.taxRate}%):</span>
                  <span className="font-mono">{formatCurrency(invoice.taxAmount)}</span>
                </div>
              )}
              <Separator className="bg-border/60" />
              <div className="flex justify-between text-sm font-bold text-foreground">
                <span>Total Due:</span>
                <span className="font-mono text-foreground">{formatCurrency(invoice.total)}</span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Amount Paid:</span>
                <span className="font-mono text-emerald-500">{formatCurrency(invoice.amountPaid)}</span>
              </div>
              <Separator className="bg-border/60" />
              <div className="flex justify-between text-sm font-bold">
                <span>Balance Due:</span>
                <span className={`font-mono ${invoice.balance > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                  {formatCurrency(invoice.balance)}
                </span>
              </div>
            </div>
          </div>

          {/* Payment History */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <History className="h-4 w-4 text-muted-foreground" />
              Payment History
            </h4>
            {invoice.payments && invoice.payments.length > 0 ? (
              <div className="rounded-xl border border-border overflow-hidden bg-background/30 text-xs">
                <table className="w-full text-left">
                  <thead className="bg-accent/30 text-[9px] uppercase font-bold text-muted-foreground tracking-wider border-b border-border">
                    <tr>
                      <th className="py-2 px-3">Date</th>
                      <th className="py-2 px-3">Method</th>
                      <th className="py-2 px-3">Ref</th>
                      <th className="py-2 px-3 text-right">Amount</th>
                      <th className="py-2 px-3 text-right">Refunded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {invoice.payments.map((payment) => (
                      <tr key={payment.id} className="hover:bg-accent/10 transition-colors">
                        <td className="py-2 px-3 text-muted-foreground font-mono">{payment.date}</td>
                        <td className="py-2 px-3 capitalize text-foreground font-medium">
                          {payment.method.replace('_', ' ')}
                        </td>
                        <td className="py-2 px-3 text-muted-foreground font-mono">{payment.reference || '-'}</td>
                        <td className="py-2 px-3 text-right font-bold font-mono text-emerald-500">
                          {formatCurrency(payment.amount)}
                        </td>
                        <td className="py-2 px-3 text-right">
                          {payment.refundedAmount > 0 && (
                            <span className="text-muted-foreground font-mono text-[9px]">
                              -{formatCurrency(payment.refundedAmount)}
                            </span>
                          )}
                          {payment.refundedAmount < payment.amount && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-1.5 text-[9px] text-foreground hover:text-destructive"
                              onClick={() => onRefund(payment)}
                            >
                              Refund
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border/80 p-4 text-center text-xs text-muted-foreground bg-accent/5">
                No payments recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="pt-6 border-t border-border/50 mt-6 flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 border-border bg-background hover:bg-accent text-foreground text-xs"
              onClick={onDownload}
            >
              <Download className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />
              Download Receipt
            </Button>
            {isDraft && (
              <Button
                variant="outline"
                className="flex-1 border-border bg-background hover:bg-accent text-foreground text-xs"
                onClick={onSend}
              >
                <Send className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />
                Send Invoice
              </Button>
            )}
          </div>
          {isPayable && (
            <Button
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-5 text-sm"
              onClick={() => {
                onOpenChange(false);
                onRecordPayment();
              }}
            >
              <DollarSign className="mr-1 h-4 w-4" />
              Record Payment
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
