// ============================================
// CoreDent - Contact / Support (public legal page)
// ============================================

import { LegalLayout } from '@/components/legal/LegalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Mail, LifeBuoy, ShieldAlert } from 'lucide-react';

export default function Contact() {
  return (
    <LegalLayout title="Contact &amp; Support">
      <div className="grid gap-4 md:grid-cols-3 not-prose">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <LifeBuoy className="h-4 w-4" /> Support
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            <p>Need help using CoreDent?</p>
            <p className="font-medium">support@coredent.example</p>
            <p className="text-muted-foreground">Mon–Fri, 9am–6pm (response &lt; 1 business day)</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mail className="h-4 w-4" /> Billing &amp; account
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            <p>Subscriptions, invoices, refunds, closing an account.</p>
            <p className="font-medium">billing@coredent.example</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldAlert className="h-4 w-4" /> Security (private)
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            <p>Report vulnerabilities responsibly — do not use public channels.</p>
            <p className="font-medium">security@coredent.example</p>
            <p className="text-muted-foreground">See SECURITY.md for safe-harbor terms.</p>
          </CardContent>
        </Card>
      </div>

      <h2 className="text-xl font-semibold pt-6">Data deletion &amp; account closure</h2>
      <p>
        To close your clinic account and request deletion or export of your data, email
        billing from the account-owner address. We verify ownership, provide a full data
        export, and process deletion per the retention schedule in our{' '}
        <a href="/legal/privacy" className="text-primary hover:underline">Privacy Policy</a>.
      </p>
    </LegalLayout>
  );
}
