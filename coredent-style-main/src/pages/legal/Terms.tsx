// ============================================
// CoreDent - Terms of Service (public legal page)
// NOTE: template copy — must be reviewed by a healthcare attorney
// before onboarding paying Practices.
// ============================================

import { LegalLayout } from '@/components/legal/LegalLayout';

export default function Terms() {
  return (
    <LegalLayout title="Terms of Service" lastUpdated="September 10, 2026">
      <p>
        These Terms govern the use of the CoreDent practice-management service.
        By creating an account you agree to them on behalf of your Practice.
      </p>

      <h2 className="text-xl font-semibold pt-4">1. The Service</h2>
      <p>
        CoreDent provides scheduling, patient records, clinical charting, billing and
        communication tools for dental practices, billed as a subscription.
      </p>

      <h2 className="text-xl font-semibold pt-4">2. Accounts &amp; responsibilities</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li>You are responsible for the accuracy of patient records you enter.</li>
        <li>You are responsible for managing your staff accounts and their roles.</li>
        <li>You must keep credentials confidential and report suspected compromises promptly.</li>
        <li>You remain the owner of your patient data at all times.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">3. Acceptable use</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li>Do not use the Service for anything unlawful.</li>
        <li>Do not attempt to access other Practices&apos; data or interfere with the Service.</li>
        <li>Do not upload malicious files (uploads are scanned and rejected).</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">4. Subscriptions &amp; payment</h2>
      <p>
        Subscriptions renew automatically until canceled. If a payment fails we may
        suspend access after the grace period described at checkout. See our{' '}
        <a href="/legal/refunds" className="text-primary hover:underline">Refund Policy</a>.
      </p>

      <h2 className="text-xl font-semibold pt-4">5. Availability &amp; support</h2>
      <p>
        We target high availability but do not guarantee uninterrupted service. Planned
        maintenance is announced in advance where practical.
      </p>

      <h2 className="text-xl font-semibold pt-4">6. Termination</h2>
      <p>
        You may cancel at any time from Settings &gt; Subscription. We may suspend accounts
        that violate these Terms or whose subscription remains unpaid. You can export your
        data before closure.
      </p>

      <h2 className="text-xl font-semibold pt-4">7. Liability</h2>
      <p>
        The Service is provided &quot;as is&quot; without warranties to the extent permitted by law.
        CoreDent is not liable for indirect or consequential damages. Our aggregate liability
        is limited to the fees you paid in the 12 months preceding the claim.
      </p>

      <h2 className="text-xl font-semibold pt-4">8. Changes</h2>
      <p>
        We will notify account owners by email at least 14 days before material changes
        take effect.
      </p>
    </LegalLayout>
  );
}
