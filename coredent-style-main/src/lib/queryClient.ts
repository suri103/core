import { QueryClient } from '@tanstack/react-query';

// ============================================
// CoreDent PMS - Shared React Query client
// ============================================
// Lives in its own module (not App.tsx) so AuthContext can import it without
// an App -> AuthContext -> App import cycle. AuthContext clears the cache on
// every logout so cached PHI (patients, dashboard, billing) never bleeds into
// the next session in the same tab.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
