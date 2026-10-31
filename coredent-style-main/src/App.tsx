import { Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';
import { Toaster } from '@/components/ui/toaster';
import { ErrorBoundary } from '@/components/error-boundary';
import { publicRoutes, protectedRoutes, notFoundRoute } from '@/routes/config';
import { Loader2 } from 'lucide-react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppShell } from '@/components/layout/AppShell';
import { TooltipProvider } from '@/components/ui/tooltip';
import { PwaInstallPrompt } from '@/components/PwaInstallPrompt';
import { PwaUpdatePrompt } from '@/components/PwaUpdatePrompt';
import { queryClient } from '@/lib/queryClient';

function AppRoutes() {
  const mainProtectedRoutes = protectedRoutes.filter(
    (route) => route.path !== '/force-change-password'
  );
  const standaloneProtectedRoutes = protectedRoutes.filter(
    (route) => route.path === '/force-change-password'
  );

  return (
    <Routes>
      {/* Public routes */}
      {publicRoutes.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={
            <Suspense fallback={<PageLoader />}>
              <route.component />
            </Suspense>
          }
        />
      ))}

      {/* Main protected routes wrapped in AppShell (Sidebar + Header + Layout) */}
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        {mainProtectedRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <ProtectedRoute roles={route.roles}>
                <Suspense fallback={<PageLoader />}>
                  <route.component />
                </Suspense>
              </ProtectedRoute>
            }
          />
        ))}
      </Route>

      {/* Standalone protected routes (e.g. first login force password change) */}
      {standaloneProtectedRoutes.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={
            <ProtectedRoute roles={route.roles}>
              <Suspense fallback={<PageLoader />}>
                <route.component />
              </Suspense>
            </ProtectedRoute>
          }
        />
      ))}

      {/* 404 */}
      <Route
        path={notFoundRoute.path}
        element={
          <Suspense fallback={<PageLoader />}>
            <notFoundRoute.component />
          </Suspense>
        }
      />
    </Routes>
  );
}

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={150}>
          <BrowserRouter>
            <AuthProvider>
              <AppRoutes />
              <PwaInstallPrompt />
              <PwaUpdatePrompt />
              <Toaster />
            </AuthProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

