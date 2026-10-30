import { Construction } from 'lucide-react';

/**
 * DemoBanner
 * ----------
 * Historical: was used to mark pages that ran on mock data. The component
 * is kept for backward compatibility with any page that might still import
 * it, but it is now a *build-time* no-op in production.
 *
 * SECURITY: A demo banner in a production build is a foot-gun. Even
 * though no current page imports this component, a future contributor
 * could ``import { DemoBanner } from '...'`` and ship a confusing UX
 * to paying customers. The build-time check below prevents that.
 */
export function DemoBanner() {
  // Vite replaces ``import.meta.env.PROD`` with ``true`` at build time,
  // so this whole expression is dead-code-eliminated in production
  // builds (no banner component code in the bundle).
  if (import.meta.env.PROD) {
    return null;
  }
  return (
    <div className="flex items-center gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg mb-6">
      <Construction className="h-5 w-5 text-amber-600 flex-shrink-0" />
      <p className="text-sm text-amber-800 dark:text-amber-200">
        <strong>Demo Mode:</strong> This page uses simulated data. Full API integration is coming soon.
      </p>
    </div>
  );
}
