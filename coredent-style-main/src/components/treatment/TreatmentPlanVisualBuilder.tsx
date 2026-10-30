import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { TreatmentPlan, TreatmentPlanUpdateInput, TreatmentStatus } from '@/types/treatmentPlan';
import { Loader2, Save, X } from 'lucide-react';

interface TreatmentPlanVisualBuilderProps {
  plan: TreatmentPlan;
  onUpdate: (data: TreatmentPlanUpdateInput) => Promise<void>;
  onCancel: () => void;
}

const ALLOWED_STATUS_TRANSITIONS: Record<TreatmentStatus, TreatmentStatus[]> = {
  draft: ['draft', 'presented', 'cancelled'],
  presented: ['presented', 'accepted', 'partially_accepted', 'declined', 'cancelled'],
  accepted: ['accepted', 'in_progress', 'cancelled'],
  partially_accepted: ['partially_accepted', 'accepted', 'in_progress', 'cancelled'],
  declined: ['declined'],
  in_progress: ['in_progress', 'completed', 'cancelled'],
  completed: ['completed'],
  cancelled: ['cancelled'],
};

export function TreatmentPlanVisualBuilder({ plan, onUpdate, onCancel }: TreatmentPlanVisualBuilderProps) {
  const availableStatuses = ALLOWED_STATUS_TRANSITIONS[plan.status];
  const [isSaving, setIsSaving] = useState(false);
  const [title, setTitle] = useState(plan.title);
  const [treatmentGoals, setTreatmentGoals] = useState(plan.treatmentGoals || '');
  const [status, setStatus] = useState<TreatmentStatus>(plan.status);
  const [notes, setNotes] = useState(plan.notes || '');

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onUpdate({
        title,
        treatmentGoals: treatmentGoals.trim() || undefined,
        status,
        notes: notes.trim() || undefined,
      });
      onCancel();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col justify-between h-[75vh] py-2 space-y-6">
      <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar flex-1">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="builder-title" className="text-xs font-black uppercase tracking-widest text-slate-400">
              Plan Title
            </Label>
            <Input
              id="builder-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="h-12 rounded-xl border-slate-200 font-bold"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="builder-status" className="text-xs font-black uppercase tracking-widest text-slate-400">
              Treatment Status
            </Label>
            <Select value={status} onValueChange={(value) => setStatus(value as TreatmentStatus)}>
              <SelectTrigger id="builder-status" className="h-12 rounded-xl border-slate-200 font-bold">
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent>
                {availableStatuses.map((value) => (
                  <SelectItem key={value} value={value}>{value.replaceAll('_', ' ')}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="builder-goals" className="text-xs font-black uppercase tracking-widest text-slate-400">
            Treatment Goals
          </Label>
          <Textarea
            id="builder-goals"
            value={treatmentGoals}
            onChange={(event) => setTreatmentGoals(event.target.value)}
            placeholder="Clinical goals for this treatment plan…"
            className="min-h-[120px] rounded-xl border-slate-200 font-medium p-4"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="builder-notes" className="text-xs font-black uppercase tracking-widest text-slate-400">
            Internal Notes
          </Label>
          <Textarea
            id="builder-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Notes for the dental team…"
            className="min-h-[180px] rounded-xl border-slate-200 font-medium p-4"
          />
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-slate-100 shrink-0">
        <Button type="button" variant="outline" onClick={onCancel} className="rounded-xl font-bold h-12 border-slate-200 px-6 flex items-center gap-1">
          <X className="w-4 h-4" /> Close
        </Button>
        <Button onClick={handleSave} disabled={isSaving || !title.trim()} className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12 px-8 flex items-center justify-center gap-2">
          {isSaving ? <><Loader2 className="w-5 h-5 animate-spin" /> Saving…</> : <><Save className="w-5 h-5" /> Save Treatment Plan</>}
        </Button>
      </div>
    </div>
  );
}
