import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { Plus, Trash2 } from 'lucide-react';
import { patientsApi } from '@/services/api';

interface LineItemInput {
  description: string;
  quantity: number;
  unitPrice: number;
}

interface CreateInvoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taxRatePercent?: number;
  paymentTermsDays?: number;
  onSubmit: (data: {
    patientId: string;
    patientName: string;
    patientEmail?: string;
    patientPhone?: string;
    lineItems: LineItemInput[];
    taxRatePercent?: number;
    dueDate: string;
    notes?: string;
  }) => Promise<boolean>;
}

function dateAfterDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function CreateInvoiceDialog({
  open,
  onOpenChange,
  onSubmit,
  taxRatePercent,
  paymentTermsDays = 30,
}: CreateInvoiceDialogProps) {
  const { data: patientsResponse } = useQuery({
    queryKey: ['patients', 'list-simple'],
    queryFn: () => patientsApi.list({ limit: 100 }),
    enabled: open,
  });
  const patients = patientsResponse?.success && patientsResponse.data?.data
    ? patientsResponse.data.data
    : [];

  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lineItems, setLineItems] = useState<LineItemInput[]>([
    { description: '', quantity: 1, unitPrice: 0 },
  ]);

  useEffect(() => {
    if (!open) return;
    setDueDate(dateAfterDays(paymentTermsDays));
    setSelectedPatientId('');
    setNotes('');
    setLineItems([{ description: '', quantity: 1, unitPrice: 0 }]);
  }, [open, paymentTermsDays]);

  const subtotal = lineItems.reduce(
    (sum, item) => sum + item.quantity * item.unitPrice,
    0,
  );
  const taxAmount = taxRatePercent === undefined
    ? undefined
    : subtotal * (taxRatePercent / 100);
  const total = taxAmount === undefined ? undefined : subtotal + taxAmount;

  const updateLineItem = (
    index: number,
    field: keyof LineItemInput,
    value: string,
  ) => {
    setLineItems(current => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      return {
        ...item,
        [field]: field === 'description' ? value : Number(value),
      };
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const patient = patients.find(item => item.id === selectedPatientId);
    if (!patient) return;

    setIsSubmitting(true);
    try {
      const succeeded = await onSubmit({
        patientId: patient.id,
        patientName: `${patient.firstName} ${patient.lastName}`.trim(),
        patientEmail: patient.email,
        patientPhone: patient.phone,
        lineItems,
        taxRatePercent,
        dueDate,
        notes: notes || undefined,
      });
      if (succeeded) onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-card/95 border border-border backdrop-blur-md text-foreground">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Create Invoice</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="patientSelect">Patient</Label>
              <Select value={selectedPatientId} onValueChange={setSelectedPatientId} required>
                <SelectTrigger id="patientSelect" className="bg-background/60 border-border">
                  <SelectValue placeholder="Select patient..." />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  {patients.map(patient => (
                    <SelectItem key={patient.id} value={patient.id}>
                      {patient.firstName} {patient.lastName} ({patient.email || 'No email'})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="dueDate">Due Date</Label>
              <Input
                id="dueDate"
                type="date"
                value={dueDate}
                onChange={event => setDueDate(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold">Invoice Items</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setLineItems(items => [
                  ...items,
                  { description: '', quantity: 1, unitPrice: 0 },
                ])}
              >
                <Plus className="h-4 w-4 mr-1" /> Add Item
              </Button>
            </div>
            <div className="space-y-3 border border-border/40 rounded-xl p-4 bg-accent/10">
              {lineItems.map((item, index) => (
                <div key={index} className="grid grid-cols-12 gap-2 items-end">
                  <div className="col-span-7">
                    <Label htmlFor={`item-description-${index}`}>Description</Label>
                    <Input
                      id={`item-description-${index}`}
                      value={item.description}
                      onChange={event => updateLineItem(index, 'description', event.target.value)}
                      placeholder="Procedure or item description"
                      required
                    />
                  </div>
                  <div className="col-span-2">
                    <Label htmlFor={`item-quantity-${index}`}>Qty</Label>
                    <Input
                      id={`item-quantity-${index}`}
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={event => updateLineItem(index, 'quantity', event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-span-2">
                    <Label htmlFor={`item-price-${index}`}>Unit Price</Label>
                    <Input
                      id={`item-price-${index}`}
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.unitPrice}
                      onChange={event => updateLineItem(index, 'unitPrice', event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-span-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="Remove item"
                      disabled={lineItems.length === 1}
                      onClick={() => setLineItems(items => items.filter((_, i) => i !== index))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="notes">Invoice Notes / Memo</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={event => setNotes(event.target.value)}
              />
            </div>
            <div className="rounded-xl border border-border/60 p-4 space-y-3 text-sm">
              <div className="flex justify-between">
                <span>Subtotal</span><span>${subtotal.toFixed(2)}</span>
              </div>
              {taxAmount === undefined ? (
                <p className="text-xs text-muted-foreground">
                  The server will apply the practice tax preference when this invoice is created.
                </p>
              ) : (
                <>
                  <div className="flex justify-between">
                    <span>Tax ({taxRatePercent}%)</span><span>${taxAmount.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-bold border-t pt-2">
                    <span>Total Due</span><span>${total?.toFixed(2)}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !selectedPatientId}>
              {isSubmitting ? 'Creating...' : 'Create Invoice'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
