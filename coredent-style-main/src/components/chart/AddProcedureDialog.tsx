import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface AddProcedureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  toothNumber: number;
  toothName: string;
  onSubmit: (procedure: any) => void;
}

const CDT_CODES = [
  { code: 'D0120', name: 'Periodic Oral Evaluation', price: 65, desc: 'Regular recall exam' },
  { code: 'D1110', name: 'Prophylaxis - Adult', price: 95, desc: 'Teeth cleaning' },
  { code: 'D2140', name: 'Amalgam Restoration - 1 Surface', price: 150, desc: 'Silver filling' },
  { code: 'D2391', name: 'Resin Composite - 1 Surface', price: 180, desc: 'White filling' },
  { code: 'D2750', name: 'Crown - Porcelain Fused to Metal', price: 1100, desc: 'Tooth cap' },
  { code: 'D3300', name: 'Root Canal Therapy - Anterior', price: 750, desc: 'Root canal treatment' },
  { code: 'D7140', name: 'Extraction - Erupted Tooth', price: 190, desc: 'Tooth pulling' },
];

export function AddProcedureDialog({
  open,
  onOpenChange,
  toothNumber,
  toothName,
  onSubmit,
}: AddProcedureDialogProps) {
  const [selectedCode, setSelectedCode] = useState(CDT_CODES[0]!.code);
  const [surface, setSurface] = useState<string>('O');
  const [notes, setNotes] = useState('');
  const [customPrice, setCustomPrice] = useState('');

  const handleSelectCode = (val: string) => {
    setSelectedCode(val);
    const codeObj = CDT_CODES.find((c) => c.code === val);
    if (codeObj) {
      setCustomPrice(codeObj.price.toString());
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const codeObj = CDT_CODES.find((c) => c.code === selectedCode);
    if (!codeObj) return;

    onSubmit({
      code: codeObj.code,
      description: codeObj.name,
      surface: surface || undefined,
      cost: customPrice ? parseFloat(customPrice) : codeObj.price,
      notes: notes.trim() || undefined,
      status: 'planned' as const,
      date: new Date().toISOString(),
    });

    // Reset fields
    setNotes('');
    setSurface('O');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] rounded-3xl p-8">
        <DialogHeader>
          <DialogTitle className="text-xl font-black text-slate-800 tracking-tight">
            Add Procedure to Tooth #{toothNumber}
          </DialogTitle>
          <DialogDescription className="font-bold text-slate-400 text-xs mt-0.5">
            {toothName}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleFormSubmit} className="space-y-5 py-4">
          {/* Procedure Code select */}
          <div className="space-y-2">
            <Label htmlFor="code" className="text-xs font-black uppercase tracking-widest text-slate-400">
              CDT Procedure Code
            </Label>
            <Select value={selectedCode} onValueChange={handleSelectCode}>
              <SelectTrigger id="code" className="h-12 rounded-xl border-slate-200 font-bold">
                <SelectValue placeholder="Select procedure" />
              </SelectTrigger>
              <SelectContent>
                {CDT_CODES.map((c) => (
                  <SelectItem key={c.code} value={c.code}>
                    {c.code} — {c.name} (${c.price})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Surface & Cost Row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="surface" className="text-xs font-black uppercase tracking-widest text-slate-400">
                Surface (Optional)
              </Label>
              <Select value={surface} onValueChange={setSurface}>
                <SelectTrigger id="surface" className="h-12 rounded-xl border-slate-200 font-bold">
                  <SelectValue placeholder="Surface" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="O">Occlusal (O)</SelectItem>
                  <SelectItem value="M">Mesial (M)</SelectItem>
                  <SelectItem value="D">Distal (D)</SelectItem>
                  <SelectItem value="F">Facial (F)</SelectItem>
                  <SelectItem value="L">Lingual (L)</SelectItem>
                  <SelectItem value="MO">Mesial-Occlusal (MO)</SelectItem>
                  <SelectItem value="DO">Distal-Occlusal (DO)</SelectItem>
                  <SelectItem value="MOD">MOD</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="price" className="text-xs font-black uppercase tracking-widest text-slate-400">
                Est. Price ($)
              </Label>
              <Input
                id="price"
                type="number"
                value={customPrice || CDT_CODES[0]!.price.toString()}
                onChange={(e) => setCustomPrice(e.target.value)}
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes" className="text-xs font-black uppercase tracking-widest text-slate-400">
              Clinical Notes
            </Label>
            <Input
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. slight bleeding on disto-lingual margin..."
              className="h-12 rounded-xl border-slate-200 font-medium"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="rounded-xl font-bold h-12 border-slate-200"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12"
            >
              Log Procedure
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
