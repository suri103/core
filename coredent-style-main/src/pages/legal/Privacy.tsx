// ============================================
// CoreDent - Privacy Policy (public legal page)
// NOTE: template copy — must be reviewed by a healthcare attorney
// before processing real patient data (see PRODUCTION_STATUS.md).
// ============================================

import { Link } from 'react-router-dom';
import { LegalLayout } from '@/components/legal/LegalLayout';

export default function Privacy() {
  return (
    <LegalLayout title="Privacy Policy" lastUpdated="September 10, 2026">
      <p>
        CoreDent (&quot;we&quot;, &quot;us&quot;) provides dental practice-management software to
        clinics (&quot;Practices&quot;). When a Practice uses CoreDent, personal and health
        information about patients is processed <strong>on behalf of the Practice</strong>.
        The Practice is the data controller; CoreDent is the processor.
      </p>

      <h2 className="text-xl font-semibold pt-4">1. Information we process</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li><strong>Account data:</strong> name, email, practice details of Practice users.</li>
        <li><strong>Patient data entered by Practices:</strong> contact details, dental and
        medical history, clinical notes, imaging, insurance and billing records.</li>
        <li><strong>Usage data:</strong> IP address, device/browser type, and audit-log
        events recorded for security and compliance purposes.</li>
      </ul>

      <h2 className="text-xl font-semibold pt-4">2. How we use information</h2>
      <ul className="list-disc pl-6 space-y-1">
        <li>To provide, maintain and secure the Service.</li>
        <li>To authenticate users and enforce role-based access.</li>
        <li>To bill the Practice for its subscription.</li>
        <li>To comply with legal obligations, including HIPAA where applicable.</li>
      </ul>
      <p>
        We do not sell personal information. We do not use patient health information for
        advertising or model training.
      </p>

      <h2 className="text-xl font-semibold pt-4">3. Legal bases (GDPR)</h2>
      <p>
        Where the GDPR applies: performance of a contract (providing the service), legitimate
        interests (security, fraud prevention), legal obligation, and consent where required.
      </p>

      <h2 className="text-xl font-semibold pt-4">4. HIPAA</h2>
      <p>
        CoreDent implements administrative, physical and technical safeguards designed to
        meet HIPAA Security Rule requirements for a Business Associate, including
        encryption of PHI at rest and in transit, audit logging, and access controls.
        We will only process PHI as described in our Business Associate Agreement.
      </p>

      <h2 className="text-xl font-semibold pt-4">5. Data retention &amp; deletion</h2>
      <p>
        Patient records are retained for as long as the Practice requires them. When a
        Practice closes its account, data is deleted or anonymized per our data-retention
        schedule, except where law requires longer retention.
      </p>

      <h2 className="text-xl font-semibold pt-4">6. Your rights</h2>
      <p>
        Depending on your jurisdiction you may have rights of access, correction, deletion,
        portability and objection. Practice users should contact us; patients should contact
        their Practice, which controls their records.
      </p>

      <h2 className="text-xl font-semibold pt-4">7. Contact</h2>
      <p>
        Privacy questions: <Link to="/legal/contact" className="text-primary hover:underline">contact us</Link>.
      </p>
    </LegalLayout>
  );
}
