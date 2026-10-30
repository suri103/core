import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, ArrowRight, BrainCircuit } from 'lucide-react';

interface AIClinicalAssistantProps {
  onApplyFinding: (toothNumber: number, finding: string) => void;
}

export function AIClinicalAssistant({ onApplyFinding }: AIClinicalAssistantProps) {
  const suggestions = [
    { tooth: 3, finding: 'decay', label: 'Potential interproximal caries (decay) on distal surface of tooth #3' },
    { tooth: 14, finding: 'decay', label: 'Incipient occlusal decay on tooth #14' },
  ];

  return (
    <Card className="border-none shadow-[0_20px_50px_rgba(0,0,0,0.03)] bg-gradient-to-br from-indigo-50 to-blue-50/50 border-indigo-100 rounded-3xl overflow-hidden ring-1 ring-indigo-100/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-100">
            <BrainCircuit className="w-4.5 h-4.5" />
          </div>
          <div>
            <CardTitle className="text-sm font-black text-indigo-900 tracking-tight flex items-center gap-1.5">
              AI Clinical Assistant <Sparkles className="w-4 h-4 text-amber-400 fill-amber-400" />
            </CardTitle>
            <CardDescription className="text-[10px] text-indigo-500 font-bold">
              Automated X-Ray & Chart Diagnostic Review
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {suggestions.map((s, idx) => (
          <div key={idx} className="p-3 bg-white/70 backdrop-blur-sm rounded-xl border border-indigo-100/40 space-y-2.5">
            <p className="text-[11px] font-semibold text-slate-700 leading-relaxed">
              {s.label}
            </p>
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={() => onApplyFinding(s.tooth, s.finding)}
                className="h-7 rounded-lg font-bold bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] px-3 flex items-center gap-1 shadow-sm"
              >
                Apply Finding <ArrowRight className="w-3 h-3" />
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
