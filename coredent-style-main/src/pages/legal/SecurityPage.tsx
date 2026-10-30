// ============================================
// CoreDent - Security & Trust (public legal page)
// ============================================

import { LegalLayout } from '@/components/legal/LegalLayout';

export default function SecurityPage() {
  return (
    <LegalLayout title="Security &amp; Trust" lastUpdated="September 10, 2026">
      <p>
        CoreDent is built for dental practices handling sensitive health information.
        Security is engineered into the product, not bolted on.
      </p>

      <h2 className="text-xl font-semibold pt-4">Application security</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li><strong>Encryption:</strong> PHI encrypted at rest at the field level with
        key rotation support; all traffic over TLS.</li>
        <li><strong>Authentication:</strong> bcrypt password hashing, JWT access/refresh
        with rotation, revocation blacklist, account lockout, email verification and
        forced first-login password rotation for admin-provisioned accounts.</li>
        <li><strong>Tenancy:</strong> every request is tenant-scoped and a middleware
        guard rejects any cross-tenant identifier; isolation is covered by automated
        tests.</li>
        <li><strong>Access control:</strong> role-based permissions (Owner, Admin,
        Dentist, Hygienist, Front Desk, Accountant) enforced server-side on every
        endpoint — not just hidden in the UI.</li>
        <li><strong>Audit trail:</strong> write-once audit logs of PHI access and
        administrative actions, with tamper-proof database triggers.</li>
        <li><strong>File security:</strong> malware scanning on upload, private
        encrypted storage, no public buckets.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">Operational security</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li>Continuous integration with dependency, secret and vulnerability scanning.</li>
        <li>Fail-closed production configuration — the service refuses to boot with
        placeholder secrets.</li>
        <li>Hourly backups, documented recovery runbooks, and disaster-recovery
        exercises.</li>
        <li>Security incident-response playbooks for compromised accounts, ransomware
        and data breach scenarios.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">Responsible disclosure</h2>
      <p>
        Found a security issue? Please report it privately to our security team via the
        contact page — we investigate every report and will not pursue legal action
        against good-faith research.
      </p>

      <h2 className="text-xl font-semibold pt-4">Compliance posture</h2>
      <p>
        CoreDent implements HIPAA-aligned safeguards (Security Rule, audit controls,
        access control, transmission security) and GDPR data-processing terms (see our{' '}
        <a href="/legal/dpa" className="text-primary hover:underline">DPA</a>). Formal
        certification and independent penetration testing are on our roadmap; see our
        public status documentation for the current posture.
      </p>
    </LegalLayout>
  );
}
