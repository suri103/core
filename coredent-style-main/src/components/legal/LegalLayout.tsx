// ============================================
// Public legal-content page shell (privacy, terms, dpa, ...)
// ============================================

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Stethoscope } from 'lucide-react';

interface LegalLayoutProps {
  title: string;
  lastUpdated?: string;
  children: ReactNode;
}

export function LegalLayout({ title, lastUpdated, children }: LegalLayoutProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Stethoscope className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-bold text-xl tracking-tight">CoreDent</span>
          </Link>
          <nav className="flex gap-4 text-sm font-medium text-muted-foreground">
            <Link to="/legal/privacy" className="hover:text-primary transition-colors">Privacy</Link>
            <Link to="/legal/terms" className="hover:text-primary transition-colors">Terms</Link>
            <Link to="/legal/dpa" className="hover:text-primary transition-colors">DPA</Link>
            <Link to="/legal/security" className="hover:text-primary transition-colors">Security</Link>
            <Link to="/legal/refunds" className="hover:text-primary transition-colors">Refunds</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 py-12">
        <div className="container max-w-3xl mx-auto px-4">
          <h1 className="text-3xl font-bold mb-2">{title}</h1>
          {lastUpdated && (
            <p className="text-sm text-muted-foreground mb-8">Last updated: {lastUpdated}</p>
          )}
          <div className="prose prose-sm dark:prose-invert max-w-none space-y-6 text-foreground">
            {children}
          </div>
        </div>
      </main>

      <footer className="border-t bg-muted/40 py-6">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <span>© 2026 CoreDent PMS. All rights reserved.</span>
          <span>
            Questions? <Link to="/legal/contact" className="text-primary hover:underline">Contact us</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
