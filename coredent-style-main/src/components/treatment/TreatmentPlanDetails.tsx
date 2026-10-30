import { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { calculatePlanSummary } from '@/types/treatmentPlan';
import type {
  ProcedureType,
  TreatmentPlan,
  TreatmentProcedureCreateInput,
} from '@/types/treatmentPlan';
import { Plus, Check, Trash2, FileText, Loader2 } from 'lucide-react';

interface TreatmentPlanDetailsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: TreatmentPlan | null;
  onAddProcedure: (data: TreatmentProcedureCreateInput) => Promise<void>;
  onCompleteProcedure: (procedureId: string) => Promise<void>;
  onDeleteProcedure: (procedureId: string) => Promise<void>;
  canModify?: boolean;
  canDelete?: boolean;
}

const PROCEDURE_TYPES: ProcedureType[] = [
  'preventive',
  'diagnostic',
  'restorative',
  'endodontic',
  'periodontal',
  'prosthodontic',
  'oral_surgery',
  'orthodontic',
  'cosmetic',
  'other',
];

function formatAmount(value: number | null): string {
  return value === null ? 'Unavailable' : `$${value.toLocaleString()}`;
}

export function TreatmentPlanDetails({
  open,
  onOpenChange,
  plan,
  onAddProcedure,
  onCompleteProcedure,
  onDeleteProcedure,
  canModify = true,
  canDelete = true,
}: TreatmentPlanDetailsProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [procedureType, setProcedureType] = useState<ProcedureType>('restorative');
  const [tooth, setTooth] = useState('');
  const [phaseId, setPhaseId] = useState('unassigned');
  const [fee, setFee] = useState('');

  if (!plan) return null;

  const summary = calculatePlanSummary(plan);

  const handleAddProcedure = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!code.trim() || !description.trim() || fee === '') return;
    setIsSubmitting(true);
    try {
      await onAddProcedure({
        procedureType,
        adaCode: code.trim(),
        description: description.trim(),
        toothNumber: tooth.trim() || undefined,
        phaseId: phaseId === 'unassigned' ? undefined : phaseId,
        fee: Number(fee),
        status: 'planned',
      });
      setCode('');
      setDescription('');
      setProcedureType('restorative');
      setTooth('');
      setPhaseId('unassigned');
      setFee('');
      setIsAdding(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const groups = [
    ...plan.phases.map((phase) => ({ id: phase.id, label: phase.phaseName })),
    { id: 'unassigned', label: 'Unassigned' },
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[650px] overflow-y-auto custom-scrollbar p-8">
        <SheetHeader className="pb-4 border-b border-slate-100">
          <div className="flex justify-between items-start">
            <div>
              <SheetTitle className="text-2xl font-black text-slate-800 tracking-tight">{plan.title}</SheetTitle>
              <SheetDescription className="font-bold text-slate-400 text-xs mt-0.5">
                Patient: {plan.patientName || 'Name unavailable'} · Provider: {plan.providerName || 'Name unavailable'}
              </SheetDescription>
            </div>
            <Badge variant="outline" className="font-black uppercase tracking-wider text-[9px] bg-slate-50 text-slate-500 border-none capitalize px-3 py-1">
              {plan.status.replaceAll('_', ' ')}
            </Badge>
          </div>
        </SheetHeader>

        <div className="py-6 space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-50/50 rounded-2xl p-4 text-center border border-slate-50">
            <div>
              <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Total Plan</span>
              <p className="font-black text-slate-800 text-sm mt-0.5">{formatAmount(summary.totalEstimatedCost)}</p>
            </div>
            <div>
              <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Insurance Est.</span>
              <p className="font-black text-emerald-600 text-sm mt-0.5">{formatAmount(summary.totalInsuranceEstimate)}</p>
            </div>
            <div>
              <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Patient Net</span>
              <p className="font-black text-blue-600 text-sm mt-0.5">{formatAmount(summary.totalPatientResponsibility)}</p>
            </div>
            <div>
              <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Completed</span>
              <p className="font-black text-slate-700 text-sm mt-0.5">${summary.totalCompleted.toLocaleString()}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-black uppercase tracking-widest text-slate-400 text-[10px]">Plan Procedures</h3>
              {canModify && (
                <Button
                  size="sm"
                  onClick={() => setIsAdding(!isAdding)}
                  className="h-8 rounded-lg font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1 text-[11px]"
                >
                  <Plus className="w-3.5 h-3.5" /> Inline Add
                </Button>
              )}
            </div>

            {isAdding && (
              <form onSubmit={handleAddProcedure} className="p-4 border border-blue-100 rounded-2xl bg-blue-50/20 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">ADA Code</Label>
                    <Input value={code} onChange={(event) => setCode(event.target.value)} placeholder="e.g. D2391" minLength={4} maxLength={10} required />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Tooth #</Label>
                    <Input value={tooth} onChange={(event) => setTooth(event.target.value)} placeholder="e.g. 14" />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Description</Label>
                  <Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Resin Composite - 1 Surface" required />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Type</Label>
                    <Select value={procedureType} onValueChange={(value) => setProcedureType(value as ProcedureType)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {PROCEDURE_TYPES.map((type) => (
                          <SelectItem key={type} value={type}>{type.replaceAll('_', ' ')}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Phase</Label>
                    <Select value={phaseId} onValueChange={setPhaseId}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="unassigned">Unassigned</SelectItem>
                        {plan.phases.map((phase) => (
                          <SelectItem key={phase.id} value={phase.id}>{phase.phaseName}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Fee ($)</Label>
                    <Input value={fee} onChange={(event) => setFee(event.target.value)} type="number" min="0" step="0.01" placeholder="180" required />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => setIsAdding(false)}>Cancel</Button>
                  <Button type="submit" size="sm" disabled={isSubmitting}>
                    {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Log Procedure'}
                  </Button>
                </div>
              </form>
            )}

            {plan.procedures.length === 0 ? (
              <p className="text-xs text-slate-400 font-medium py-8 text-center bg-slate-50/50 rounded-2xl border border-dashed border-slate-100">
                No procedures mapped to this treatment plan.
              </p>
            ) : (
              groups.map((group) => {
                const procedures = plan.procedures.filter((procedure) =>
                  group.id === 'unassigned' ? !procedure.phaseId : procedure.phaseId === group.id,
                );
                if (procedures.length === 0) return null;
                return (
                  <div key={group.id} className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-700 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100/50">
                      {group.label}
                    </h4>
                    <div className="space-y-2 pl-1">
                      {procedures.map((procedure) => (
                        <div key={procedure.id} className="p-3 border border-slate-50 rounded-xl hover:border-slate-200 transition-colors flex items-center justify-between gap-4">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${procedure.status === 'completed' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-50 text-slate-500'}`}>
                              {procedure.status === 'completed' ? <Check className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                            </div>
                            <div>
                              <p className="text-xs font-bold text-slate-800">
                                {procedure.adaCode} — {procedure.description}
                                {procedure.toothNumber && <span className="text-[10px] text-blue-500 font-bold ml-1.5">Tooth #{procedure.toothNumber}</span>}
                              </p>
                              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                                Fee: ${procedure.fee.toLocaleString()} · {procedure.procedureType.replaceAll('_', ' ')}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {canModify && procedure.status === 'planned' && (
                              <Button size="sm" variant="ghost" onClick={() => onCompleteProcedure(procedure.id)} className="h-7 px-2 text-[10px] font-bold text-emerald-600 hover:bg-emerald-50">
                                Done
                              </Button>
                            )}
                            {canDelete && (
                              <Button size="icon" variant="ghost" aria-label={`Remove ${procedure.description}`} onClick={() => onDeleteProcedure(procedure.id)} className="h-7 w-7 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg">
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
