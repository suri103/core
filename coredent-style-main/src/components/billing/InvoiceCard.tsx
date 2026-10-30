import { Card, CardContent } from '@/components/ui/card';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  MoreVertical,
  DollarSign,
  Download, 
  Send, 
  Trash2, 
  Eye, 
  Calendar 
} from 'lucide-react';
import type { Invoice } from '@/types/billing';

interface InvoiceCardProps {
  invoice: Invoice;
  onView: (invoice: Invoice) => void;
  onRecordPayment: (invoice: Invoice) => void;
  onDownload: (invoice: Invoice) => void;
  onSend: (invoice: Invoice) => void;
  onDelete: (invoice: Invoice) => void;
}

export function InvoiceCard({
  invoice,
  onView,
  onRecordPayment,
  onDownload,
  onSend,
  onDelete,
}: InvoiceCardProps) {
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

  const { formatCurrency } = useCurrencyFormatter();

  const isDraft = invoice.status === 'draft';
  const isPayable = ['pending', 'partially_paid', 'overdue'].includes(invoice.status);
  const isCancellable = !['paid', 'cancelled'].includes(invoice.status);

  return (
    <Card className="overflow-hidden border border-border bg-card/60 backdrop-blur-md transition-all duration-300 hover:shadow-lg hover:border-primary/30 group">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold tracking-tight text-muted-foreground">
                {invoice.invoiceNumber}
              </span>
              <Badge variant="outline" className={`${getStatusColor(invoice.status)} capitalize border px-2 py-0`}>
                {invoice.status.replace('_', ' ')}
              </Badge>
            </div>
            <h3 className="font-semibold text-lg tracking-tight text-foreground transition-colors group-hover:text-primary">
              {invoice.patientName}
            </h3>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">Open menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-card/90 backdrop-blur-md border border-border">
              <DropdownMenuItem onClick={() => onView(invoice)} className="gap-2 cursor-pointer">
                <Eye className="h-4 w-4 text-muted-foreground" />
                View Details
              </DropdownMenuItem>
              {isPayable && (
                <DropdownMenuItem onClick={() => onRecordPayment(invoice)} className="gap-2 cursor-pointer">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  Record Payment
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => onDownload(invoice)} className="gap-2 cursor-pointer">
                <Download className="h-4 w-4 text-muted-foreground" />
                Download Receipt
              </DropdownMenuItem>
              {isDraft && (
                <DropdownMenuItem onClick={() => onSend(invoice)} className="gap-2 cursor-pointer">
                  <Send className="h-4 w-4 text-muted-foreground" />
                  Send Invoice
                </DropdownMenuItem>
              )}
              {isCancellable && (
                <>
                  <DropdownMenuSeparator className="bg-border" />
                  <DropdownMenuItem
                    onClick={() => onDelete(invoice)}
                    className="gap-2 cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                    Cancel Invoice
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Dates */}
        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border/50 pt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground/75" />
            <span>Issued: {invoice.issueDate}</span>
          </div>
          <div className="flex items-center gap-1.5 justify-end">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground/75" />
            <span>Due: {invoice.dueDate || 'Not set'}</span>
          </div>
        </div>

        {/* Amount details */}
        <div className="mt-5 grid grid-cols-2 gap-4 rounded-lg bg-accent/30 p-3 backdrop-blur-sm">
          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">Total</span>
            <span className="text-base font-bold text-foreground">{formatCurrency(invoice.total)}</span>
          </div>
          <div className="text-right">
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">Balance Due</span>
            <span className={`text-base font-bold ${invoice.balance > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
              {formatCurrency(invoice.balance)}
            </span>
          </div>
        </div>

        {/* Bottom micro-actions */}
        <div className="mt-5 flex gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1 text-xs border-border/80 bg-background/50 hover:bg-accent backdrop-blur-sm"
            onClick={() => onView(invoice)}
          >
            <Eye className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />
            Details
          </Button>
          {isPayable && (
            <Button 
              size="sm" 
              className="flex-1 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
              onClick={() => onRecordPayment(invoice)}
            >
              <DollarSign className="mr-1 h-3.5 w-3.5" />
              Pay
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
