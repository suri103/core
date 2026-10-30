// Analytics Integration
// PostHog for product analytics
//
// L-2 FIX: ``_PHI_BLOCKED_KEYS`` is a hard deny-list applied to every
// event payload and every ``identify`` call. PostHog captures anything
// passed to ``capture()` or ``identify()`` server-side, so any caller
// that includes a patient name, email, phone, DOB, or any field that
// mentions the words ``name``, ``email``, ``phone``, ``dob``, ``ssn``,
// or ``address`` will be silently stripped. Operational metadata
// (userId, role, practiceId, feature names, counters) flows through
// unchanged.

import { logger } from './logger';

// Keys we refuse to forward to PostHog. The values can still flow
// (a ``userId`` is a UUID, not a name); the *keys* are the leak.
const _PHI_BLOCKED_KEYS: ReadonlySet<string> = new Set([
  'email',
  'practiceName',
  'practice_name',
  'firstName',
  'first_name',
  'lastName',
  'last_name',
  'fullName',
  'full_name',
  'patientName',
  'patient_name',
  'phone',
  'dob',
  'dateOfBirth',
  'date_of_birth',
  'address',
  'homeAddress',
  'home_address',
  'ssn',
  'insuranceMemberId',
  'insurance_member_id',
  'patientEmail',
  'patient_email',
  'patientPhone',
  'patient_phone',
  'patientDob',
  'patient_dob',
  'name',
]);

// Substring denylist for keys we did not anticipate. The cost of
// over-blocking here is one extra property in a product dashboard;
// the cost of under-blocking is a PHI leak. ``patientId`` is a UUID
// and is intentionally NOT on this list; it is safe operational data.
const _PHI_SUBSTRINGS: readonly string[] = [
  'patientName',
  'patient_name',
  'patientEmail',
  'patient_email',
  'patientPhone',
  'patient_phone',
  'patientDob',
  'patient_dob',
  'practiceName',
  'practice_name',
  'insurance',
  'address',
];

function _is_phikey(key: string): boolean {
  if (_PHI_BLOCKED_KEYS.has(key)) {
    return true;
  }
  const k = key.toLowerCase();
  return _PHI_SUBSTRINGS.some((needle) => k.includes(needle));
}

function _redact_phi(
  properties: Record<string, unknown>,
): Record<string, unknown> {
  if (!properties) {
    return properties;
  }
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(properties)) {
    if (_is_phikey(key)) {
      continue;
    }
    out[key] = value;
  }
  return out;
}

interface PostHogWindow extends Window {
  posthog?: {
    identify: (userId: string, properties: Record<string, unknown>) => void;
    capture: (event: string, properties?: Record<string, unknown>) => void;
    reset: () => void;
    people: {
      set: (properties: Record<string, unknown>) => void;
    };
  };
}

interface AnalyticsEvent {
  event: string;
  properties?: Record<string, unknown>;
}

interface UserProperties {
  userId?: string;
  email?: string;
  role?: string;
  practiceId?: string;
  practiceName?: string;
  [key: string]: unknown;
}

class Analytics {
  private enabled: boolean;
  private userId: string | null = null;

  constructor() {
    this.enabled = !import.meta.env.DEV && import.meta.env.VITE_ANALYTICS_ENABLED === 'true';
  }

  /**
   * Initialize analytics with user information
   */
  identify(userId: string, properties: UserProperties = {}) {
    if (!this.enabled) return;

    this.userId = userId;

    // L-2 FIX: strip PHI before handing the payload to PostHog.
    const safeProperties = _redact_phi(properties as Record<string, unknown>);

    // PostHog identify
    const w = window as unknown as PostHogWindow;
    if (typeof window !== 'undefined' && w.posthog) {
      w.posthog.identify(userId, safeProperties);
    }
  }

  /**
   * Track an event
   */
  track(event: string, properties: Record<string, unknown> = {}) {
    if (!this.enabled) return;

    // L-2 FIX: strip PHI before handing the payload to PostHog.
    const safeProperties = _redact_phi(properties);

    const eventData: AnalyticsEvent = {
      event,
      properties: {
        ...safeProperties,
        timestamp: new Date().toISOString(),
        userId: this.userId,
      },
    };

    // PostHog track
    const w = window as unknown as PostHogWindow;
    if (typeof window !== 'undefined' && w.posthog) {
      w.posthog.capture(event, eventData.properties);
    }

    // Log in development only
    if (import.meta.env.DEV) {
      logger.debug('[Analytics]', { event, properties: eventData.properties });
    }
  }

  /**
   * Track page view
   */
  page(pageName: string, properties: Record<string, unknown> = {}) {
    this.track('Page Viewed', {
      page: pageName,
      ...properties,
    });
  }

  /**
   * Reset analytics (on logout)
   */
  reset() {
    this.userId = null;

    const w = window as unknown as PostHogWindow;
    if (typeof window !== 'undefined' && w.posthog) {
      w.posthog.reset();
    }
  }

  /**
   * Set user properties
   */
  setUserProperties(properties: UserProperties) {
    if (!this.enabled) return;

    // L-2 FIX: strip PHI before handing the payload to PostHog.
    const safeProperties = _redact_phi(properties as Record<string, unknown>);

    const w = window as unknown as PostHogWindow;
    if (typeof window !== 'undefined' && w.posthog) {
      w.posthog.people.set(safeProperties as UserProperties);
    }
  }

  /**
   * Track feature usage
   */
  trackFeature(featureName: string, action: string, properties: Record<string, unknown> = {}) {
    this.track(`Feature: ${featureName}`, {
      action,
      ...properties,
    });
  }
}

export const analytics = new Analytics();

// Common event tracking functions

export const trackSignup = (_userId: string, method: string) => {
  analytics.track('User Signed Up', { method });
};

export const trackLogin = (_userId: string, method: string) => {
  analytics.track('User Logged In', { method });
};

export const trackLogout = () => {
  analytics.track('User Logged Out', {});
  analytics.reset();
};

export const trackPatientCreated = (patientId: string) => {
  analytics.track('Patient Created', { patientId });
};

export const trackAppointmentBooked = (appointmentId: string, type: string) => {
  analytics.track('Appointment Booked', { appointmentId, type });
};

export const trackInvoiceCreated = (invoiceId: string, amount: number) => {
  analytics.track('Invoice Created', { invoiceId, amount });
};

export const trackPaymentReceived = (paymentId: string, amount: number, method: string) => {
  analytics.track('Payment Received', { paymentId, amount, method });
};

export const trackFeatureUsed = (feature: string, action: string) => {
  analytics.trackFeature(feature, action);
};

export const trackError = (error: Error, context?: Record<string, unknown>) => {
  analytics.track('Error Occurred', {
    error: error.message,
    stack: error.stack,
    ...context,
  });
};

export const trackPerformance = (metric: string, value: number) => {
  analytics.track('Performance Metric', {
    metric,
    value,
  });
};
