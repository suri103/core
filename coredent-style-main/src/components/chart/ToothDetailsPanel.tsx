import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Calendar, ShieldAlert } from 'lucide-react';
import type { ToothData, ToothCondition, ProcedureStatus } from '@/types/dentalChart';

interface ToothDetailsPanelProps {
  tooth: ToothData | null;
  onAddProcedure: () => void;
  onUpdateCondition: (condition: ToothCondition) => void;
  onUpdateProcedureStatus: (procedureId: string, status: ProcedureStatus) => void;
  onDeleteProcedure: (procedureId: string) => void;
}

export function ToothDetailsPanel({
  tooth,
  onAddProcedure,
  onUpdateCondition,
  onUpdateProcedureStatus,
  onDeleteProcedure,
}: ToothDetailsPanelProps) {
  if (!tooth) {
    return (
      <Card className="border-none shadow-[0_20px_50px_rgba(0,0,0,0.03)] bg-white/80 backdrop-blur-xl rounded-3xl overflow-hidden">
        <CardContent className="py-16 text-center text-slate-400 space-y-4">
          <div className="w-16 h-16 rounded-full bg-slate-50 flex items-center justify-center mx-auto text-slate-300">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <p className="font-bold">No tooth selected</p>
          <p className="text-xs font-medium max-w-xs mx-auto">Click any tooth on the odontogram diagram to view history or log clinical findings.</p>
        </CardContent>
      </Card>
    );
  }

  const conditions: { value: ToothCondition; label: string; icon: string }[] = [
    { value: 'sound', label: 'Sound / Healthy', icon: '🟢' },
    { value: 'decay', label: 'Caries (Decay)', icon: '🔴' },
    { value: 'filled', label: 'Restoration (Filled)', icon: '🔵' },
    { value: 'missing', label: 'Extracted (Missing)', icon: '⚫' },
    { value: 'crown', label: 'Crown / Cap', icon: '🟡' },
  ];

  return (
    <Card className="border-none shadow-[0_20px_50px_rgba(0,0,0,0.03)] bg-white/80 backdrop-blur-xl rounded-3xl overflow-hidden">
      <CardHeader className="pb-4">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-xl font-black text-slate-800 tracking-tight">
              Tooth #{tooth.number}
            </CardTitle>
            <CardDescription className="font-bold text-slate-400 text-xs mt-0.5">
              {tooth.name}
            </CardDescription>
          </div>
          <Badge variant="outline" className="font-bold uppercase tracking-wider text-[10px] bg-slate-50 text-slate-500">
            {tooth.condition}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Update Condition */}
        <div className="space-y-2">
          <Label className="text-[10px] font-black uppercase tracking-widest text-slate-400 pl-0.5">Clinical Condition</Label>
          <div className="grid grid-cols-1 gap-1.5">
            {conditions.map((cond) => {
              const isActive = tooth.condition === cond.value;
              return (
                <button
                  key={cond.value}
                  onClick={() => onUpdateCondition(cond.value)}
                  className={`w-full p-3 rounded-xl flex items-center justify-between text-xs font-bold transition-all border ${
                    isActive
                      ? 'bg-blue-600 border-blue-600 text-white shadow-lg shadow-blue-100 scale-[1.01]'
                      : 'bg-white border-slate-100 hover:border-slate-300 text-slate-700'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span>{cond.icon}</span>
                    <span>{cond.label}</span>
                  </span>
                  {isActive && <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-md">Active</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* Procedures */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          <div className="flex justify-between items-center">
            <Label className="text-[10px] font-black uppercase tracking-widest text-slate-400 pl-0.5">Procedures</Label>
            <Button
              size="sm"
              onClick={onAddProcedure}
              className="h-8 rounded-lg font-bold bg-blue-600 text-white hover:bg-blue-700 flex items-center gap-1 text-[11px]"
            >
              <Plus className="w-3.5 h-3.5" /> Log Procedure
            </Button>
          </div>

          <div className="space-y-2">
            {!tooth.procedures || tooth.procedures.length === 0 ? (
              <p className="text-xs text-slate-400 font-medium py-3 text-center bg-slate-50/50 rounded-xl border border-dashed border-slate-100">
                No procedures recorded for this tooth.
              </p>
            ) : (
              tooth.procedures.map((proc: any) => (
                <div key={proc.id} className="p-3 rounded-xl border border-slate-100 bg-white space-y-2.5">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-black text-slate-800">{proc.code || 'Procedure'}</p>
                      <p className="text-[10px] text-slate-400 font-bold">{proc.description || 'No description'}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onDeleteProcedure(proc.id)}
                      className="h-7 w-7 text-slate-400 hover:text-red-500 rounded-lg"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>

                  <div className="flex justify-between items-center text-[10px] font-bold">
                    <span className="text-slate-400 flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> {new Date(proc.date || Date.now()).toLocaleDateString()}
                    </span>

                    <div className="flex gap-1.5">
                      <button
                        onClick={() => onUpdateProcedureStatus(proc.id, 'planned')}
                        className={`px-2 py-0.5 rounded-md border ${
                          proc.status === 'planned'
                            ? 'bg-amber-50 border-amber-200 text-amber-600'
                            : 'bg-transparent border-slate-100 text-slate-400 hover:text-slate-700'
                        }`}
                      >
                        Planned
                      </button>
                      <button
                        onClick={() => onUpdateProcedureStatus(proc.id, 'completed')}
                        className={`px-2 py-0.5 rounded-md border ${
                          proc.status === 'completed'
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-600'
                            : 'bg-transparent border-slate-100 text-slate-400 hover:text-slate-700'
                        }`}
                      >
                        Done
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
