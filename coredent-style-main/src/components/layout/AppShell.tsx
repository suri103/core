// ============================================
// CoreDent PMS - Application Shell Layout
// Includes responsive Sidebar, Header, and Main Content Container
// ============================================

import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface AppShellProps {
  children?: React.ReactNode;
}

const SIDEBAR_COLLAPSED_KEY = 'coredent_sidebar_collapsed';

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();

  // Desktop sidebar collapse state, persisted in localStorage
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
    } catch {
      return false;
    }
  });

  // Mobile sidebar drawer state
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // Ignore localStorage errors
      }
      return next;
    });
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-background text-foreground">
        {/* Navigation Sidebar */}
        <Sidebar
          collapsed={collapsed}
          mobileOpen={mobileOpen}
          onToggle={toggleCollapsed}
          onMobileClose={() => setMobileOpen(false)}
        />

        {/* Main Content Area */}
        <div
          className={cn(
            'flex flex-col min-h-screen transition-[padding] duration-300 ease-in-out',
            collapsed ? 'lg:pl-16' : 'lg:pl-64'
          )}
        >
          {/* Top Header Bar */}
          <Header onMobileMenuToggle={() => setMobileOpen((prev) => !prev)} />

          {/* Page Content Container - bounded width prevents wide-screen overflow */}
          <main className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
            {children || <Outlet />}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}

export default AppShell;
