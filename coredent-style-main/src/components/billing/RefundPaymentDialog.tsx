import React, { useEffect, useMemo, useState } from 'react';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Undo2 } from 'lucide-react';
import type { Invoice, InvoicePayment } from '@/types/billing';

interface RefundPaymentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoice: Invoice | null;
  payment: InvoicePayment | null;
  onSubmit: (data: {
    paymentId: string;
    amount: number;
    reason?: string;
  }) => Promise<boolean>;
}

export function RefundPaymentDialog({
  open,
  onOpenChange,
  invoice,
  payment,
  onSubmit,
}: RefundPaymentDialogProps) {
  const { formatCurrency } = useCurrencyFormatter();

  const maxRefundable = useMemo(() => {
    if (!payment) return 0;
    return Math.max(0, payment.amount - payment.refundedAmount);
  }, [payment]);

  const [amount, setAmount] = useState<number>(maxRefundable);
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset the form whenever the dialog opens for a different payment.
  useEffect(() => {
    if (!open) return;
    setAmount(maxRefundable);
    setReason('');
  }, [open, maxRefundable]);

  if (!invoice || !payment) return null;

  const isValid = amount > 0 && amount <= maxRefundable;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isValid || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const succeeded = await onSubmit({
        paymentId: payment.id,
        amount,
        reason: reason.trim() || undefined,
      });
      if (succeeded) onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-card/95 border border-border backdrop-blur-md text-foreground">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2">
            <Undo2 className="h-5 w-5 text-primary" />
            Refund Payment
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="rounded-xl border border-border bg-accent/20 p-4 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Invoice:</span>
              <span className="font-semibold font-mono">{invoice.invoiceNumber}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Patient:</span>
              <span className="font-semibold">{invoice.patientName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Original payment:</span>
              <span className="font-semibold">{formatCurrency(payment.amount)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Already refunded:</span>
              <span className="font-semibold">{formatCurrency(payment.refundedAmount)}</span>
            </div>
            <div className="flex justify-between border-t border-border/50 pt-2 text-sm">
              <span className="text-muted-foreground">Max refundable:</span>
              <span className="font-bold text-primary">{formatCurrency(maxRefundable)}</span>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="refund-amount">Refund Amount</Label>
            <Input
              id="refund-amount"
              type="number"
              min="0.01"
              max={maxRefundable || undefined}
              step="0.01"
              value={amount || ''}
              onChange={(event) => setAmount(Number(event.target.value))}
              required
            />
            {maxRefundable > 0 && (
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs text-muted-foreground"
                  onClick={() => setAmount(maxRefundable)}
                >
                  Refund full amount
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="refund-reason">Reason</Label>
            <Textarea
              id="refund-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. Patient overcharged, duplicate payment, service not rendered"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={isSubmitting || !isValid}
            >
              {isSubmitting ? 'Refunding...' : 'Confirm Refund'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
