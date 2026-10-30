import { Building2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';

/**
 * Shows the practice the signed-in user actually belongs to. Multi-location
 * switching is not implemented against a real API yet, so this renders a
 * read-only label instead of a fake clinic picker that logged to the console
 * and changed nothing.
 */
export function LocationSwitcher() {
  const { user } = useAuth();
  const practiceName = user?.practiceName?.trim();

  if (!practiceName) return null;

  return (
    <div className="px-4 py-3 mb-2 border-b border-slate-100">
      <div className="flex items-center gap-2 mb-2 px-1">
        <Building2 className="w-4 h-4 text-slate-500" />
        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
          Active Location
        </span>
      </div>
      <div
        className="w-full bg-slate-50 border border-slate-200 font-semibold text-slate-800 h-10 rounded-xl px-3 flex items-center truncate"
        title={practiceName}
      >
        {practiceName}
      </div>
    </div>
  );
}
