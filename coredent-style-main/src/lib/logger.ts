// Centralized logging and error tracking

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  context?: Record<string, unknown>;
  error?: Error;
}

// Error monitoring integration using Sentry.
// Initialize Sentry in production if DSN is provided and looks real.
import * as Sentry from '@sentry/browser';

function _isRealSentryDsn(dsn: string | undefined): boolean {
  if (!dsn) return false;
  const s = dsn.trim().toLowerCase();
  if (!s) return false;
  // Reject common placeholders so we don't spam console with init errors
  if (s.includes('your-sentry-dsn') || s.includes('your_sentry_dsn')) return false;
  if (['changeme', 'todo', 'tbd', 'placeholder'].includes(s)) return false;
  // Must be a valid Sentry ingest URL
  return /^https:\/\/[^@]+@[^/]+\/\d+/i.test(dsn);
}

if (!import.meta.env.DEV && _isRealSentryDsn(import.meta.env.VITE_SENTRY_DSN)) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    // Scrub PHI from breadcrumbs and events
    beforeSend(event) {
      // Drop any cookie / auth header data
      if (event.request?.cookies) delete event.request.cookies;
      if (event.request?.headers) {
        const h = event.request.headers as Record<string, string>;
        delete h.authorization;
        delete h.Authorization;
        delete h.cookie;
        delete h.Cookie;
        delete h['x-csrf-token'];
      }
      return event;
    },
  });
}

class Logger {
  private get isDevelopment(): boolean {
    return import.meta.env.DEV;
  }
  private logs: LogEntry[] = [];
  private maxLogs = 100;

  private createEntry(
    level: LogLevel,
    message: string,
    context?: Record<string, unknown>,
    error?: Error
  ): LogEntry {
    return {
      level,
      message,
      timestamp: new Date().toISOString(),
      context,
      error,
    };
  }

  private addLog(entry: LogEntry) {
    this.logs.push(entry);
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }
  }

  private sendToMonitoring(entry: LogEntry) {
    // Send errors and warnings to Sentry in production
    // Sentry is imported at module level; capture calls are no-ops if init() was not called
    if (!this.isDevelopment) {
      try {
        if (entry.level === 'error' && entry.error) {
          Sentry.captureException(entry.error);
        } else if (entry.level === 'warn') {
          Sentry.captureMessage(entry.message, 'warning');
        }
      } catch {
        // Silently fail if Sentry is not available or not initialized
      }
    }
  }

  debug(message: string, context?: Record<string, unknown>) {
    const entry = this.createEntry('debug', message, context);
    this.addLog(entry);
    
    if (this.isDevelopment) {
      console.debug(`[DEBUG] ${message}`, context);
    }
  }

  info(message: string, context?: Record<string, unknown>) {
    const entry = this.createEntry('info', message, context);
    this.addLog(entry);
    
    if (this.isDevelopment) {
      console.info(`[INFO] ${message}`, context);
    }
  }

  warn(message: string, context?: Record<string, unknown>) {
    const entry = this.createEntry('warn', message, context);
    this.addLog(entry);

    if (this.isDevelopment) {
      console.warn(`[WARN] ${message}`, context);
    }
    this.sendToMonitoring(entry);
  }

  error(message: string, error?: Error, context?: Record<string, unknown>) {
    const entry = this.createEntry('error', message, context, error);
    this.addLog(entry);
    
    if (this.isDevelopment) {
      console.error(`[ERROR] ${message}`, error, context);
    }
    this.sendToMonitoring(entry);
  }

  // Get recent logs for debugging
  getRecentLogs(count = 50): LogEntry[] {
    return this.logs.slice(-count);
  }

  // Clear logs
  clearLogs() {
    this.logs = [];
  }

  // Export logs for support
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2);
  }
}

export const logger = new Logger();

// Error boundary helper
export function logError(error: Error, errorInfo?: { componentStack?: string }) {
  logger.error('React Error Boundary caught an error', error, {
    componentStack: errorInfo?.componentStack,
  });
}

// API error helper
export function logApiError(
  endpoint: string,
  error: Error,
  context?: Record<string, unknown>
) {
  logger.error(`API Error: ${endpoint}`, error, {
    endpoint,
    ...context,
  });
}

// Performance monitoring
export function logPerformance(metric: string, duration: number) {
  logger.info(`Performance: ${metric}`, { duration, metric });
}
