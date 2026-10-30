// Performance and User Monitoring
// Tracks user interactions, performance metrics, and application health

import { logger } from './logger';

interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

interface UserAction {
  action: string;
  component: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

/**
 * Scrub potential PHI/PII (emails, long digit sequences like phone/SSN,
 * UUIDs) from a string before it leaves the app via analytics.
 */
function scrubPotentialPhi(input: string): string {
  return input
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[redacted-email]')
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, '[redacted-id]')
    .replace(/\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b/g, '[redacted-ssn]')
    .replace(/\b\+?\d[\d\s().-]{7,}\d\b/g, '[redacted-number]')
    .slice(0, 200);
}

class MonitoringService {
  private metrics: PerformanceMetric[] = [];
  private actions: UserAction[] = [];
  private maxEntries = 100;
  private isDevelopment = import.meta.env.DEV;

  /**
   * Track a performance metric
   */
  trackMetric(name: string, value: number, metadata?: Record<string, unknown>) {
    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      metadata,
    };

    this.metrics.push(metric);
    if (this.metrics.length > this.maxEntries) {
      this.metrics.shift();
    }

    // Log slow operations
    if (value > 1000) {
      logger.warn(`Slow operation detected: ${name}`, { value, metadata });
    }

    // Send to analytics in production
    if (!this.isDevelopment) {
      this.sendToAnalytics('metric', metric);
    }
  }

  /**
   * Track user action
   */
  trackAction(action: string, component: string, metadata?: Record<string, unknown>) {
    const userAction: UserAction = {
      action,
      component,
      timestamp: Date.now(),
      metadata,
    };

    this.actions.push(userAction);
    if (this.actions.length > this.maxEntries) {
      this.actions.shift();
    }

    if (this.isDevelopment) {
      logger.debug(`User action: ${action} in ${component}`, metadata);
    }

    // Send to analytics in production
    if (!this.isDevelopment) {
      this.sendToAnalytics('action', userAction);
    }
  }

  /**
   * Track page view
   */
  trackPageView(path: string, title?: string) {
    this.trackAction('page_view', 'router', { path, title });
  }

  /**
   * Track API call performance
   */
  trackApiCall(endpoint: string, duration: number, status: number) {
    this.trackMetric('api_call', duration, { endpoint, status });
  }

  /**
   * Track component render time
   */
  trackComponentRender(component: string, duration: number) {
    this.trackMetric('component_render', duration, { component });
  }

  /**
   * Track user session duration
   */
  trackSessionDuration(duration: number) {
    this.trackMetric('session_duration', duration);
  }

  /**
   * Track feature usage
   */
  trackFeatureUsage(feature: string, metadata?: Record<string, unknown>) {
    this.trackAction('feature_used', feature, metadata);
  }

  /**
   * Track error occurrence
   */
  trackError(error: Error, context?: Record<string, unknown>) {
    logger.error('Tracked error', error, context);
    // HIPAA: error messages/stacks can contain PHI (patient names, emails,
    // record IDs). Never forward them to third-party analytics — send only
    // the error name and a scrubbed, length-capped message.
    this.trackAction('error_occurred', 'error_boundary', {
      error_name: error.name,
      message: scrubPotentialPhi(error.message),
      ...context,
    });
  }

  /**
   * Get recent metrics
   */
  getMetrics(count = 50): PerformanceMetric[] {
    return this.metrics.slice(-count);
  }

  /**
   * Get recent actions
   */
  getActions(count = 50): UserAction[] {
    return this.actions.slice(-count);
  }

  /**
   * Get average metric value
   */
  getAverageMetric(name: string): number {
    const filtered = this.metrics.filter(m => m.name === name);
    if (filtered.length === 0) return 0;
    
    const sum = filtered.reduce((acc, m) => acc + m.value, 0);
    return sum / filtered.length;
  }

  /**
   * Clear all monitoring data
   */
  clear() {
    this.metrics = [];
    this.actions = [];
  }

  /**
   * Export monitoring data for debugging
   */
  export(): string {
    return JSON.stringify({
      metrics: this.metrics,
      actions: this.actions,
      timestamp: Date.now(),
    }, null, 2);
  }

  /**
   * Send data to analytics service
   */
  private sendToAnalytics(type: 'metric' | 'action', data: PerformanceMetric | UserAction) {
    // Google Analytics 4
    if (typeof window !== 'undefined' && (window as any).gtag) {
      const gtag = (window as any).gtag;
      
      if (type === 'metric') {
        const metric = data as PerformanceMetric;
        gtag('event', metric.name, {
          value: metric.value,
          ...metric.metadata,
        });
      } else {
        const action = data as UserAction;
        gtag('event', action.action, {
          component: action.component,
          ...action.metadata,
        });
      }
    }

    // Mixpanel
    if (typeof window !== 'undefined' && (window as any).mixpanel) {
      const mixpanel = (window as any).mixpanel;
      
      if (type === 'metric') {
        const metric = data as PerformanceMetric;
        mixpanel.track(metric.name, {
          value: metric.value,
          ...metric.metadata,
        });
      } else {
        const action = data as UserAction;
        mixpanel.track(action.action, {
          component: action.component,
          ...action.metadata,
        });
      }
    }

    // Custom analytics endpoint — only enabled when explicitly configured,
    // otherwise we would POST every action to a non-existent endpoint and
    // pollute the error logs with 404s.
    const analyticsEndpoint = import.meta.env.VITE_ANALYTICS_ENDPOINT;
    if (analyticsEndpoint) {
      fetch(analyticsEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, data }),
        // Don't block user navigation on analytics
        keepalive: true,
      }).catch(() => {
        // Silently fail if analytics endpoint is unavailable
      });
    }
  }
}

export const monitoring = new MonitoringService();

/**
 * React hook for tracking component lifecycle
 */
export function useMonitoring(componentName: string) {
  const startTime = Date.now();

  return {
    trackAction: (action: string, metadata?: Record<string, unknown>) => {
      monitoring.trackAction(action, componentName, metadata);
    },
    trackMount: () => {
      const duration = Date.now() - startTime;
      monitoring.trackComponentRender(componentName, duration);
    },
  };
}

/**
 * Higher-order function to track async operations
 */
export function trackAsync<T>(
  name: string,
  fn: () => Promise<T>,
  metadata?: Record<string, unknown>
): Promise<T> {
  const startTime = Date.now();
  
  return fn()
    .then(result => {
      const duration = Date.now() - startTime;
      monitoring.trackMetric(name, duration, { ...metadata, success: true });
      return result;
    })
    .catch(error => {
      const duration = Date.now() - startTime;
      monitoring.trackMetric(name, duration, { ...metadata, success: false });
      throw error;
    });
}
