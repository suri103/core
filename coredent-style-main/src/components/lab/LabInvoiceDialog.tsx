import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import type { LabVendor, LabInvoiceRecord } from '@/services/labsApi';

interface CreateProps {
  mode: 'create';
  open: boolean;
  onOpenChange: (open: boolean) => void;
  labs: LabVendor[];
  onSubmit: (data: {
    lab_id: string;
    subtotal: number;
    tax?: number;
    shipping?: number;
    discount?: number;
    due_date?: string;
    notes?: string;
  }) => Promise<boolean>;
}

interface PayProps {
  mode: 'pay';
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoice: LabInvoiceRecord;
  onSubmit: (data: {
    amount: number;
    transaction_id: string;
    notes?: string;
  }) => Promise<boolean>;
}

type Props = CreateProps | PayProps;

export function LabInvoiceDialog(props: Props) {
  const isCreate = props.mode === 'create';
  const [labId, setLabId] = useState('');
  const [subtotal, setSubtotal] = useState('');
  const [tax, setTax] = useState('0');
  const [shipping, setShipping] = useState('0');
  const [discount, setDiscount] = useState('0');
  const [dueDate, setDueDate] = useState('');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (props.open) {
      if (props.mode === 'create') {
        setLabId(''); setSubtotal(''); setTax('0'); setShipping('0');
        setDiscount('0'); setDueDate(''); setNotes('');
      } else {
        setAmount(''); setNotes('');
        setTransactionId(crypto.randomUUID());
      }
    }
  }, [props.open, props.mode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      let ok = false;
      if (isCreate) {
        if (!labId) return;
        ok = await (props as CreateProps).onSubmit({
          lab_id: labId,
          subtotal: Number(subtotal) || 0,
          tax: Number(tax) || 0,
          shipping: Number(shipping) || 0,
          discount: Number(discount) || 0,
          due_date: dueDate || undefined,
          notes: notes.trim() || undefined,
        });
      } else {
        const pay = props as PayProps;
        const max = Number(pay.invoice.total ?? 0) - Number(pay.invoice.amount_paid ?? 0);
        if (!amount || Number(amount) <= 0 || Number(amount) > max || !transactionId) return;
        ok = await pay.onSubmit({
          amount: Number(amount),
          transaction_id: transactionId,
          notes: notes.trim() || undefined,
        });
      }
      if (ok) props.onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isCreate ? 'Create Lab Invoice' : 'Record Lab Invoice Payment'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {isCreate ? (
            <>
              <div className="space-y-1">
                <Label>Lab *</Label>
                <Select value={labId} onValueChange={setLabId}>
                  <SelectTrigger><SelectValue placeholder="Select lab" /></SelectTrigger>
                  <SelectContent>
                    {(props as CreateProps).labs.map((l) => (
                      <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>Subtotal *</Label>
                  <Input type="number" min="0" step="0.01" value={subtotal} onChange={(e) => setSubtotal(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Tax</Label>
                  <Input type="number" min="0" step="0.01" value={tax} onChange={(e) => setTax(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Shipping</Label>
                  <Input type="number" min="0" step="0.01" value={shipping} onChange={(e) => setShipping(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Discount</Label>
                  <Input type="number" min="0" step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Due Date</Label>
                  <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-1">
                <Label>Invoice</Label>
                <div className="text-sm text-muted-foreground">
                  {(props as PayProps).invoice.invoice_number ?? ""} — balance{' '}
                  {((Number((props as PayProps).invoice.total ?? 0)) - (Number((props as PayProps).invoice.amount_paid ?? 0))).toLocaleString(undefined, { style: 'currency', currency: 'USD' })}
                </div>
              </div>
              <div className="space-y-1">
                <Label>Amount *</Label>
                <Input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
              </div>
            </>
          )}
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => props.onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : (isCreate ? 'Create Invoice' : 'Record Payment')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
