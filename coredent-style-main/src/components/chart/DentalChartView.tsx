import { cn } from '@/lib/utils';
import type { ToothData, ToothCondition } from '@/types/dentalChart';

interface DentalChartViewProps {
  teeth: ToothData[];
  selectedTooth: number | null;
  onSelectTooth: (number: number) => void;
}

export function DentalChartView({ teeth, selectedTooth, onSelectTooth }: DentalChartViewProps) {
  // Upper arch: teeth 1-16
  const upperTeeth = teeth.filter((t) => t.number >= 1 && t.number <= 16);
  // Lower arch: teeth 17-32 (sorted backward or normally, standard is left to right)
  const lowerTeeth = teeth.filter((t) => t.number >= 17 && t.number <= 32);

  const getConditionColor = (condition: ToothCondition) => {
    switch (condition) {
      case 'decay':
        return 'bg-red-100 border-red-500 text-red-700 hover:bg-red-200';
      case 'filled':
        return 'bg-emerald-100 border-emerald-500 text-emerald-700 hover:bg-emerald-200';
      case 'missing':
        return 'bg-slate-100 border-slate-300 text-slate-400 opacity-50 hover:bg-slate-200';
      case 'crown':
        return 'bg-amber-100 border-amber-500 text-amber-700 hover:bg-amber-200';
      default:
        return 'bg-white border-slate-200 text-slate-700 hover:border-blue-400 hover:bg-blue-50/20';
    }
  };

  const getConditionBadge = (condition: ToothCondition) => {
    switch (condition) {
      case 'decay':
        return '🚨';
      case 'filled':
        return '💎';
      case 'missing':
        return '❌';
      case 'crown':
        return '👑';
      default:
        return '';
    }
  };

  const renderArch = (archTeeth: ToothData[]) => {
    return (
      <div className="grid grid-cols-8 md:grid-cols-16 gap-2 py-4">
        {archTeeth.map((tooth) => {
          const isSelected = selectedTooth === tooth.number;
          return (
            <button
              key={tooth.number}
              onClick={() => onSelectTooth(tooth.number)}
              className={cn(
                'flex flex-col items-center justify-between p-2 rounded-xl border-2 transition-all h-24 focus:outline-none focus:ring-2 focus:ring-blue-500',
                isSelected ? 'ring-4 ring-blue-500/20 border-blue-600 bg-blue-50 scale-105 shadow-md' : getConditionColor(tooth.condition)
              )}
            >
              <span className="text-[10px] font-black text-slate-400">#{tooth.number}</span>
              
              {/* Visual Tooth Representation */}
              <div className="w-8 h-8 flex items-center justify-center font-bold text-lg relative">
                🦷
                {tooth.condition !== 'sound' && (
                  <span className="absolute -bottom-1 -right-1 text-xs">{getConditionBadge(tooth.condition)}</span>
                )}
              </div>

              <span className="text-[9px] font-bold tracking-tight text-center line-clamp-1 max-w-full">
                {tooth.name.split(' ')[0]}
              </span>
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <div className="bg-white/80 backdrop-blur-xl border border-slate-100 shadow-[0_20px_50px_rgba(0,0,0,0.03)] rounded-3xl p-6 space-y-6">
      <div>
        <h3 className="text-lg font-black text-slate-800 tracking-tight flex items-center gap-2">
          Interactive Odontogram <span className="text-xs text-blue-500 font-bold bg-blue-50 px-2.5 py-0.5 rounded-full">3D Mapping</span>
        </h3>
        <p className="text-xs text-slate-400 font-medium">Click any tooth to examine history, log findings, or schedule procedures.</p>
      </div>

      <div className="space-y-4 divide-y divide-slate-100">
        <div>
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-2 pl-1">Maxillary Arch (Upper)</span>
          {renderArch(upperTeeth)}
        </div>
        <div className="pt-6">
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-2 pl-1">Mandibular Arch (Lower)</span>
          {renderArch(lowerTeeth)}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-slate-100 text-xs font-bold text-slate-500">
        <span className="text-slate-400">Legend:</span>
        <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-md border border-slate-200 bg-white" /> Sound</span>
        <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-md border border-red-500 bg-red-100" /> Decay</span>
        <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-md border border-emerald-500 bg-emerald-100" /> Filled</span>
        <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-md border border-slate-300 bg-slate-100" /> Missing</span>
        <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded-md border border-amber-500 bg-amber-100" /> Crown</span>
      </div>
    </div>
  );
}
