// ============================================
// CoreDent - Refund / Cancellation Policy (public legal page)
// Covers the Practice's CoreDent subscription only —
// patient billing refunds are handled inside each Practice.
// ============================================

import { LegalLayout } from '@/components/legal/LegalLayout';

export default function RefundPolicy() {
  return (
    <LegalLayout title="Refund &amp; Cancellation Policy" lastUpdated="September 10, 2026">
      <p>
        This policy covers your CoreDent <strong>subscription</strong>. Refunds you issue
        to your own patients are managed inside your practice&apos;s billing module and
        are not covered here.
      </p>

      <h2 className="text-xl font-semibold pt-4">1. Canceling</h2>
      <p>
        You can cancel your subscription any time from Settings &gt; Subscription.
        Access continues until the end of the paid period; no further charges occur.
      </p>

      <h2 className="text-xl font-semibold pt-4">2. Refund eligibility</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li><strong>14-day money back:</strong> first-time subscribers may request a
        full refund within 14 days of the initial charge.</li>
        <li><strong>Service failure:</strong> if a verified, material outage prevents
        use of the core service for more than 24 hours in a billing month, we issue a
        pro-rata credit.</li>
        <li><strong>Billing errors:</strong> duplicate or incorrect charges are
        refunded in full once verified.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">3. Non-refundable</h2>
      <p>
        Usage-based charges already consumed, custom onboarding or data-migration
        services already performed, and months elapsed beyond the 14-day window are
        not refundable, but you keep access until period end.
      </p>

      <h2 className="text-xl font-semibold pt-4">4. How to request</h2>
      <p>
        Email billing from the address on the account with your clinic name and the
        reason. Approved refunds return to the original payment method within 5–10
        business days.
      </p>

      <h2 className="text-xl font-semibold pt-4">5. Account closure &amp; data</h2>
      <p>
        On closure you can export your data. We retain a minimal billing record for tax
        purposes and delete/anonymize patient data per our retention schedule.
      </p>
    </LegalLayout>
  );
}
