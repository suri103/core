import { useLocation } from 'react-router-dom';
import { ArrowLeft, FileText, Megaphone, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface ProductStatus {
  title: string;
  description: string;
  icon: typeof FileText;
  links: { label: string; href: string }[];
}

const STATUS_BY_PATH: Record<string, ProductStatus> = {
  '/documents': {
    title: 'Documents and signatures',
    description: 'This staff workspace is not enabled until tenant-scoped document storage and signature actions are connected. No sample patient documents are shown.',
    icon: FileText,
    links: [{ label: 'Return to Dashboard', href: '/dashboard' }],
  },
  '/marketing': {
    title: 'Marketing automation',
    description: 'Marketing automation is not enabled for this practice yet. Campaigns, consent-aware delivery, and performance metrics will appear here once the live service is connected.',
    icon: Megaphone,
    links: [{ label: 'Return to Dashboard', href: '/dashboard' }],
  },
};

const fallbackStatus: ProductStatus = {
  title: 'Workspace unavailable',
  description: 'This workspace is not enabled for the current account.',
  icon: ShieldCheck,
  links: [{ label: 'Return to Dashboard', href: '/dashboard' }],
};

export default function ProductAvailability() {
  const { pathname } = useLocation();
  const status = STATUS_BY_PATH[pathname] || fallbackStatus;
  const Icon = status.icon;

  return <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4"><Card className="w-full max-w-2xl border-none shadow-xl"><CardContent className="space-y-6 p-8 text-center md:p-12"><div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-8 w-8" aria-hidden="true" /></div><div className="space-y-3"><h1 className="text-3xl font-black tracking-tight text-slate-900">{status.title}</h1><p className="mx-auto max-w-xl text-slate-600">{status.description}</p></div><div className="flex flex-col justify-center gap-3 sm:flex-row">{status.links.map((link) => <Button key={link.href} asChild><a href={link.href}>{link.label}</a></Button>)}<Button asChild variant="outline"><a href="/dashboard"><ArrowLeft className="mr-2 h-4 w-4" />Dashboard</a></Button></div></CardContent></Card></div>;
}
