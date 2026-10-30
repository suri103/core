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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Receipt } from 'lucide-react';
import type { Invoice, PaymentMethod } from '@/types/billing';

const methodLabels: Record<PaymentMethod, string> = {
  cash: 'Cash',
  card: 'Card',
  check: 'Check',
  insurance: 'Insurance',
  upi: 'UPI',
  other: 'Other',
};

interface RecordPaymentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoice: Invoice | null;
  acceptedPaymentMethods?: PaymentMethod[];
  onSubmit: (data: {
    amount: number;
    method: PaymentMethod;
    reference: string;
    notes?: string;
  }) => Promise<boolean>;
}

export function RecordPaymentDialog({
  open,
  onOpenChange,
  invoice,
  acceptedPaymentMethods,
  onSubmit,
}: RecordPaymentDialogProps) {
  const availableMethods = useMemo(
    () => acceptedPaymentMethods?.length
      ? acceptedPaymentMethods
      : (['cash', 'card', 'check'] as PaymentMethod[]),
    [acceptedPaymentMethods],
  );
  const preferredMethod = availableMethods.includes('card')
    ? 'card'
    : availableMethods[0];

  const [amount, setAmount] = useState(0);
  const [method, setMethod] = useState<PaymentMethod>(preferredMethod);
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open || !invoice) return;
    setAmount(invoice.balance);
    setMethod(preferredMethod);
    setReference('');
    setNotes('');
  }, [open, invoice, preferredMethod]);

  const { formatCurrency } = useCurrencyFormatter();
  if (!invoice) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedReference = reference.trim();
    if (amount <= 0 || amount > invoice.balance || !trimmedReference) return;

    setIsSubmitting(true);
    try {
      const succeeded = await onSubmit({
        amount,
        method,
        reference: trimmedReference,
        notes: notes || undefined,
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
            <Receipt className="h-5 w-5 text-primary" />
            Record Payment
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="rounded-xl border border-border bg-accent/20 p-4 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Invoice Number:</span>
              <span className="font-semibold font-mono">{invoice.invoiceNumber}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Patient Name:</span>
              <span className="font-semibold">{invoice.patientName}</span>
            </div>
            <div className="flex justify-between border-t border-border/50 pt-2 text-sm">
              <span className="text-muted-foreground">Remaining Balance:</span>
              <span className="font-bold text-rose-500">{formatCurrency(invoice.balance)}</span>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="payAmount">Payment Amount</Label>
            <Input
              id="payAmount"
              type="number"
              min="0.01"
              max={invoice.balance}
              step="0.01"
              value={amount || ''}
              onChange={event => setAmount(Number(event.target.value))}
              required
            />
            <Button type="button" variant="ghost" size="sm" onClick={() => setAmount(invoice.balance)}>
              Pay full balance
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="payMethod">Payment Method</Label>
            <Select value={method} onValueChange={value => setMethod(value as PaymentMethod)}>
              <SelectTrigger id="payMethod">
                <SelectValue placeholder="Select method..." />
              </SelectTrigger>
              <SelectContent>
                {availableMethods.map(value => (
                  <SelectItem key={value} value={value}>{methodLabels[value]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="reference">Transaction Reference</Label>
            <Input
              id="reference"
              value={reference}
              onChange={event => setReference(event.target.value)}
              placeholder="Check number, authorization, or transaction ID"
              required
            />
            <p className="text-[11px] text-muted-foreground">
              Required for manual payments so the entry can be reconciled against your records.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="payNotes">Payment Notes</Label>
            <Textarea
              id="payNotes"
              value={notes}
              onChange={event => setNotes(event.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || amount <= 0 || amount > invoice.balance || !reference.trim()}
            >
              {isSubmitting ? 'Recording...' : 'Record Payment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
