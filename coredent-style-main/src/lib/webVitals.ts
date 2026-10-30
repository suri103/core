// Web Vitals monitoring for performance tracking
import { onCLS, onFID, onFCP, onLCP, onTTFB, type Metric } from 'web-vitals';
import { logger } from './logger';

interface VitalsReport {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  id: string;
}

// Thresholds based on web.dev recommendations
const THRESHOLDS = {
  CLS: { good: 0.1, poor: 0.25 },
  FID: { good: 100, poor: 300 },
  FCP: { good: 1800, poor: 3000 },
  LCP: { good: 2500, poor: 4000 },
  TTFB: { good: 800, poor: 1800 },
};

function getRating(name: string, value: number): 'good' | 'needs-improvement' | 'poor' {
  const threshold = THRESHOLDS[name as keyof typeof THRESHOLDS];
  if (!threshold) return 'good';
  
  if (value <= threshold.good) return 'good';
  if (value <= threshold.poor) return 'needs-improvement';
  return 'poor';
}

function sendToAnalytics(metric: VitalsReport) {
  // Log to console in development
  if (import.meta.env.DEV) {
    logger.debug(`[Web Vitals] ${metric.name}`, {
      value: metric.value,
      rating: metric.rating,
      id: metric.id,
    });
  }

  // Log to monitoring service
  logger.info(`Web Vital: ${metric.name}`, {
    metric: metric.name,
    value: metric.value,
    rating: metric.rating,
    delta: metric.delta,
    id: metric.id,
  });

  // Send to analytics service (Google Analytics, etc.)
  if (typeof window !== 'undefined' && (window as any).gtag) {
    (window as any).gtag('event', metric.name, {
      event_category: 'Web Vitals',
      event_label: metric.id,
      value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
      non_interaction: true,
    });
  }
}

function handleMetric(metric: Metric) {
  const report: VitalsReport = {
    name: metric.name,
    value: metric.value,
    rating: getRating(metric.name, metric.value),
    delta: metric.delta,
    id: metric.id,
  };

  sendToAnalytics(report);
}

export function initWebVitals() {
  // Only run in browser
  if (typeof window === 'undefined') return;

  // Cumulative Layout Shift
  onCLS(handleMetric);

  // First Input Delay
  onFID(handleMetric);

  // First Contentful Paint
  onFCP(handleMetric);

  // Largest Contentful Paint
  onLCP(handleMetric);

  // Time to First Byte
  onTTFB(handleMetric);
}

// Export for manual tracking
export function trackCustomMetric(name: string, value: number) {
  logger.info(`Custom Metric: ${name}`, { metric: name, value });

  if (typeof window !== 'undefined' && (window as any).gtag) {
    (window as any).gtag('event', 'custom_metric', {
      event_category: 'Performance',
      event_label: name,
      value: Math.round(value),
      non_interaction: true,
    });
  }
}
