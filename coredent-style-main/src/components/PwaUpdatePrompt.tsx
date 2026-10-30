import { RefreshCw, X } from 'lucide-react';
import { useRegisterSW } from 'virtual:pwa-register/react';
import { Button } from '@/components/ui/button';

export function PwaUpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(r) {
      if (r) {
        // Periodic check for SW updates
        setInterval(() => {
          r.update().catch(() => {});
        }, 60 * 60 * 1000);
      }
    },
  });

  if (!needRefresh) {
    return null;
  }

  return (
    <aside
      role="alert"
      aria-label="New version available"
      className="fixed bottom-4 left-4 z-[100] flex max-w-sm items-center gap-3 rounded-xl border bg-background p-3 shadow-lg"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <RefreshCw className="h-5 w-5 text-primary" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-sm">Update Available</p>
        <p className="text-xs text-muted-foreground">A new version of CoreDent is ready.</p>
      </div>
      <Button size="sm" onClick={() => updateServiceWorker(true)}>
        Reload
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        aria-label="Dismiss update prompt"
        onClick={() => setNeedRefresh(false)}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </Button>
    </aside>
  );
}
