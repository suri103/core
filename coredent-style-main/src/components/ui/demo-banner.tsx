import { AlertTriangle } from 'lucide-react';

/**
 * Banner shown on pages that currently display demonstration data.
 * Will be removed once the page is wired to real API endpoints.
 */
export function DemoBanner() {
  if (import.meta.env.PROD) {
    return null;
  }
  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-200">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span>
        <strong>Demo Mode:</strong> This page displays sample data for demonstration purposes. Live data will appear once the backend integration is complete.
      </span>
    </div>
  );
}
