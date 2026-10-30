import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { calculatePlanSummary } from '@/types/treatmentPlan';
import type { TreatmentPlan } from '@/types/treatmentPlan';
import { Eye, Pencil, Trash2, FileText } from 'lucide-react';

interface TreatmentPlanCardProps {
  plan: TreatmentPlan;
  onView: (plan: TreatmentPlan) => void;
  onEdit: (plan: TreatmentPlan) => void;
  onDelete: (plan: TreatmentPlan) => void;
  canEdit?: boolean;
  canCancel?: boolean;
}

function formatAmount(value: number | null): string {
  return value === null ? 'Unavailable' : `$${value.toLocaleString()}`;
}

export function TreatmentPlanCard({
  plan,
  onView,
  onEdit,
  onDelete,
  canEdit = true,
  canCancel = true,
}: TreatmentPlanCardProps) {
  const summary = calculatePlanSummary(plan);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
      case 'partially_accepted':
        return 'bg-emerald-50 text-emerald-600 border-emerald-100';
      case 'in_progress':
        return 'bg-blue-50 text-blue-600 border-blue-100';
      case 'completed':
        return 'bg-purple-50 text-purple-600 border-purple-100';
      case 'declined':
      case 'cancelled':
        return 'bg-slate-100 text-slate-500 border-slate-200';
      default:
        return 'bg-amber-50 text-amber-600 border-amber-100';
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white hover:shadow-[0_20px_50px_rgba(0,0,0,0.04)] transition-shadow flex flex-col justify-between h-[280px] border border-slate-100">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start">
          <div className="space-y-1">
            <CardTitle className="text-lg font-black text-slate-800 tracking-tight leading-tight line-clamp-1">{plan.title}</CardTitle>
            <CardDescription className="text-xs text-slate-400 font-bold">
              Patient: {plan.patientName || 'Name unavailable'}
            </CardDescription>
          </div>
          <Badge variant="outline" className={`font-black uppercase tracking-wider text-[9px] px-2.5 py-0.5 border capitalize ${getStatusColor(plan.status)}`}>
            {plan.status.replaceAll('_', ' ')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 flex-1 flex flex-col justify-between">
        <div className="grid grid-cols-3 gap-2 bg-slate-50/50 rounded-2xl p-4 text-center border border-slate-50">
          <div>
            <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Total Cost</span>
            <p className="font-black text-slate-800 text-sm mt-0.5">{formatAmount(summary.totalEstimatedCost)}</p>
          </div>
          <div>
            <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Insurance</span>
            <p className="font-black text-emerald-600 text-sm mt-0.5">{formatAmount(summary.totalInsuranceEstimate)}</p>
          </div>
          <div>
            <span className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Patient Due</span>
            <p className="font-black text-blue-600 text-sm mt-0.5">{formatAmount(summary.totalPatientResponsibility)}</p>
          </div>
        </div>

        <div className="flex justify-between items-center text-xs font-bold text-slate-400">
          {plan.proceduresLoaded ? (
            <>
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5 text-slate-400" /> {plan.procedures.length} procedures
              </span>
              <span>{plan.procedures.filter((procedure) => procedure.status === 'completed').length} / {plan.procedures.length} Done</span>
            </>
          ) : (
            <span className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5 text-slate-400" /> Open plan to load procedures
            </span>
          )}
        </div>

        <div className="flex justify-between items-center pt-3 border-t border-slate-50 gap-2">
          <Button variant="ghost" size="sm" onClick={() => onView(plan)} className="flex-1 h-9 rounded-lg font-bold text-xs bg-slate-50 text-slate-600 hover:bg-slate-100 flex items-center justify-center gap-1">
            <Eye className="w-3.5 h-3.5" /> View
          </Button>
          {canEdit && (
            <Button variant="ghost" size="sm" onClick={() => onEdit(plan)} className="flex-1 h-9 rounded-lg font-bold text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 flex items-center justify-center gap-1">
              <Pencil className="w-3.5 h-3.5" /> Designer
            </Button>
          )}
          {canCancel && (
            <Button variant="ghost" size="icon" aria-label={`Cancel ${plan.title}`} onClick={() => onDelete(plan)} className="h-9 w-9 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50">
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
