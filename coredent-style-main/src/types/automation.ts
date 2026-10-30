export type AutomationEvent =
  | 'appointment_booked'
  | 'appointment_cancelled'
  | 'appointment_completed'
  | 'appointment_confirmed'
  | 'appointment_no_show'
  | 'patient_created'
  | 'patient_registered'
  | 'invoice_created'
  | 'invoice_overdue'
  | 'payment_received'
  | 'payment_refunded'
  | 'review_request'
  | 'treatment_plan_approved'
  | 'treatment_plan_created';

export interface AutomationWebhook {
  id: string;
  name: string;
  url: string;
  event: AutomationEvent;
  isActive: boolean;
  /**
   * Write-only. The API never returns a stored secret (audit finding H-14:
   * the webhook list used to include `secretToken` verbatim for any
   * authenticated user). Send a value to set or replace it; omit it to leave
   * the stored secret untouched. Read `hasSecretToken` to know whether one is
   * configured.
   */
  secretToken?: string;
  /** Write-only, same contract as `secretToken`. */
  headers?: Record<string, string>;
  /** Read-only: whether a secret token is configured. */
  hasSecretToken?: boolean;
  /** Read-only: names (not values) of configured custom headers. */
  customHeaderNames?: string[];
  createdAt?: string;
  updatedAt?: string;
}

export type AutomationPayload = Record<string, any>;
