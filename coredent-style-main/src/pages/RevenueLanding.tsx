import { BarChart3, CreditCard, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/**
 * Compatibility landing page for legacy imports.
 *
 * Revenue figures are rendered by the live Reports and Billing pages. Keeping
 * this component free of sample KPIs prevents an old deep link from showing
 * fabricated financial data.
 */
export default function RevenueLanding() {
  return <div className="container mx-auto space-y-6 py-6">
    <div><h1 className="text-3xl font-bold">Revenue workspace</h1><p className="text-muted-foreground">Use the live reports and billing workspaces for tenant-scoped financial data.</p></div>
    <div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5" />Reports</CardTitle></CardHeader><CardContent><p className="mb-4 text-sm text-muted-foreground">Review production, collections, outstanding balances, and utilization from the reports API.</p><Button asChild><Link to="/reports">Open Reports</Link></Button></CardContent></Card><Card><CardHeader><CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5" />Billing</CardTitle></CardHeader><CardContent><p className="mb-4 text-sm text-muted-foreground">Manage invoices and recorded payments from the billing API.</p><Button asChild variant="outline"><Link to="/billing"><FileText className="mr-2 h-4 w-4" />Open Billing</Link></Button></CardContent></Card></div>
  </div>;
}
