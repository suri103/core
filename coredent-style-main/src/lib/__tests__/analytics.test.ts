import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  analytics,
  trackSignup,
  trackLogin,
  trackLogout,
  trackPatientCreated,
  trackAppointmentBooked,
  trackInvoiceCreated,
  trackPaymentReceived,
  trackFeatureUsed,
  trackError,
  trackPerformance,
} from '../analytics';

describe('Analytics Service', () => {
  const mockPosthog = {
    identify: vi.fn(),
    capture: vi.fn(),
    reset: vi.fn(),
    people: {
      set: vi.fn(),
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (window as any).posthog = mockPosthog;
  });

  afterEach(() => {
    delete (window as any).posthog;
    vi.restoreAllMocks();
  });

  describe('disabled in development mode', () => {
    it('does not call posthog identify, capture, reset, or set properties', () => {
      // In dev mode (default test environment), analytics is disabled
      analytics.identify('user-1', { role: 'admin' });
      expect(mockPosthog.identify).not.toHaveBeenCalled();

      analytics.track('some_event', { x: 1 });
      expect(mockPosthog.capture).not.toHaveBeenCalled();

      analytics.setUserProperties({ email: 'test@example.com' });
      expect(mockPosthog.people.set).not.toHaveBeenCalled();

      analytics.reset();
      expect(mockPosthog.reset).toHaveBeenCalled();
    });
  });

  describe('enabled in production mode', () => {
    beforeEach(() => {
      vi.stubEnv('DEV', false as any);
      vi.stubEnv('PROD', true as any);
      vi.stubEnv('VITE_ANALYTICS_ENABLED', 'true' as any);
    });

    it('identifies and tracks events', async () => {
      vi.resetModules();
      const { analytics: prodAnalytics } = await import('../analytics');

      prodAnalytics.identify('user-1', { role: 'admin' });
      expect(mockPosthog.identify).toHaveBeenCalledWith('user-1', { role: 'admin' });

      prodAnalytics.track('some_event', { x: 1 });
      expect(mockPosthog.capture).toHaveBeenCalledWith('some_event', expect.objectContaining({
        x: 1,
        userId: 'user-1',
        timestamp: expect.any(String),
      }));
    });

    it('sets user properties', async () => {
      vi.resetModules();
      const { analytics: prodAnalytics } = await import('../analytics');

      prodAnalytics.setUserProperties({ role: 'admin' });
      expect(mockPosthog.people.set).toHaveBeenCalledWith({ role: 'admin' });
    });

    it('redacts PHI keys from identify, track, and setUserProperties payloads', async () => {
      // L-2 FIX: PHI must never reach PostHog even if a future caller
      // accidentally includes a ``patientEmail`` or ``phone`` field.
      vi.resetModules();
      const { analytics: prodAnalytics } = await import('../analytics');

      prodAnalytics.identify('user-1', {
        role: 'admin',
        email: 'leak@example.com',          // should be stripped
        practiceName: 'Bright Smile',         // should be stripped
        patientId: 'p-1',                    // should pass through
        patientEmail: 'leak2@example.com',   // should be stripped
      });
      expect(mockPosthog.identify).toHaveBeenCalledWith('user-1', {
        role: 'admin',
        patientId: 'p-1',
      });

      prodAnalytics.track('Patient Viewed', {
        patientId: 'p-1',
        patientEmail: 'leak3@example.com',
        firstName: 'John',
        appointmentId: 'a-1',
      });
      const trackCall = mockPosthog.capture.mock.calls.find(
        (call) => call[0] === 'Patient Viewed',
      );
      expect(trackCall).toBeDefined();
      expect(trackCall![1]).toEqual(
        expect.objectContaining({
          patientId: 'p-1',
          appointmentId: 'a-1',
        }),
      );
      expect(trackCall![1]).not.toHaveProperty('patientEmail');
      expect(trackCall![1]).not.toHaveProperty('firstName');

      prodAnalytics.setUserProperties({
        role: 'admin',
        email: 'should-be-stripped@example.com',
        phone: '555-1234',
      });
      expect(mockPosthog.people.set).toHaveBeenLastCalledWith({ role: 'admin' });
    });

    it('resets user session', async () => {
      vi.resetModules();
      const { analytics: prodAnalytics } = await import('../analytics');

      prodAnalytics.reset();
      expect(mockPosthog.reset).toHaveBeenCalled();
    });
  });

  describe('common tracking helper functions', () => {
    // We can test the helper functions by spying on the main analytics.track method
    it('triggers appropriate track calls for helpers', () => {
      const trackSpy = vi.spyOn(analytics, 'track').mockImplementation(() => {});
      const resetSpy = vi.spyOn(analytics, 'reset').mockImplementation(() => {});
      const trackFeatureSpy = vi.spyOn(analytics, 'trackFeature').mockImplementation(() => {});

      trackSignup('u1', 'email');
      expect(trackSpy).toHaveBeenCalledWith('User Signed Up', { method: 'email' });

      trackLogin('u1', 'google');
      expect(trackSpy).toHaveBeenCalledWith('User Logged In', { method: 'google' });

      trackLogout();
      expect(trackSpy).toHaveBeenCalledWith('User Logged Out', {});
      expect(resetSpy).toHaveBeenCalled();

      trackPatientCreated('p1');
      expect(trackSpy).toHaveBeenCalledWith('Patient Created', { patientId: 'p1' });

      trackAppointmentBooked('a1', 'Exam');
      expect(trackSpy).toHaveBeenCalledWith('Appointment Booked', { appointmentId: 'a1', type: 'Exam' });

      trackInvoiceCreated('inv1', 150);
      expect(trackSpy).toHaveBeenCalledWith('Invoice Created', { invoiceId: 'inv1', amount: 150 });

      trackPaymentReceived('pay1', 50, 'cash');
      expect(trackSpy).toHaveBeenCalledWith('Payment Received', { paymentId: 'pay1', amount: 50, method: 'cash' });

      trackFeatureUsed('charting', 'select_tooth');
      expect(trackFeatureSpy).toHaveBeenCalledWith('charting', 'select_tooth');

      const err = new Error('boom');
      trackError(err, { component: 'App' });
      expect(trackSpy).toHaveBeenCalledWith('Error Occurred', expect.objectContaining({
        error: 'boom',
        stack: err.stack,
        component: 'App',
      }));

      trackPerformance('render_latency', 15);
      expect(trackSpy).toHaveBeenCalledWith('Performance Metric', { metric: 'render_latency', value: 15 });
    });
  });
});
