// ============================================
// CoreDent - Data Processing Addendum (public legal page)
// NOTE: template copy — sign-off from a healthcare attorney and
// customer-specific signature blocks are required before use.
// ============================================

import { LegalLayout } from '@/components/legal/LegalLayout';

export default function Dpa() {
  return (
    <LegalLayout title="Data Processing Addendum (DPA)" lastUpdated="September 10, 2026">
      <p>
        This DPA is incorporated into the Terms of Service and applies where CoreDent
        processes personal data or PHI on behalf of a Practice.
      </p>

      <h2 className="text-xl font-semibold pt-4">1. Roles</h2>
      <p>
        The Practice is the controller. CoreDent is the processor. Where HIPAA applies,
        the Practice is a Covered Entity and CoreDent a Business Associate.
      </p>

      <h2 className="text-xl font-semibold pt-4">2. Processing instructions</h2>
      <p>
        CoreDent processes data only to provide the Service, as documented here and in
        the HIPAA Business Associate Agreement where executed.
      </p>

      <h2 className="text-xl font-semibold pt-4">3. Security measures</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li>Encryption of PHI at rest (field-level, key rotation supported) and in transit (TLS).</li>
        <li>Multi-tenant isolation enforced at request level and per-query tenant scoping.</li>
        <li>Role-based access control and write-once audit logging.</li>
        <li>Rate limiting, lockout and CSRF protections on all state-changing APIs.</li>
        <li>Malware scanning of file uploads; encrypted, access-controlled storage.</li>
        <li>Backups with RPO 1 hour / RTO 4 hours, tested monthly.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">4. Sub-processors</h2>
      <p>
        CoreDent uses the following categories of sub-processors, under data-protection
        terms and (for HIPAA customers) Business Associate Agreements: cloud hosting,
        payment processing, transactional email/SMS delivery, error monitoring, and
        cloud storage. An up-to-date list is available on request.
      </p>

      <h2 className="text-xl font-semibold pt-4">5. Data subject requests</h2>
      <p>
        CoreDent assists the Practice in responding to access, correction and deletion
        requests within the statutory time window.
      </p>

      <h2 className="text-xl font-semibold pt-4">6. Breach notification</h2>
      <p>
        CoreDent notifies the Practice without undue delay (and within statutory
        deadlines for PHI) upon confirming a breach affecting the Practice&apos;s data,
        with the facts, scope and remediation plan.
      </p>

      <h2 className="text-xl font-semibold pt-4">7. Return &amp; deletion</h2>
      <p>
        On termination the Practice may export its data. After the retention window,
        data is deleted or anonymized and backups rotate out per schedule.
      </p>
    </LegalLayout>
  );
}
