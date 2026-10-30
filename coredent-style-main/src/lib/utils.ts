import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Converts an object to URLSearchParams, filtering out undefined/null values.
 * Arrays are joined by commas.
 */
export function toURLSearchParams(
  params: Record<string, unknown>,
): URLSearchParams {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    if (Array.isArray(value)) {
      if (value.length > 0) {
        searchParams.append(key, value.join(","));
      }
    } else {
      searchParams.append(key, String(value));
    }
  });

  return searchParams;
}

/**
 * Formats a number as currency.
 *
 * This is the single place money formatting happens; every call site passes
 * the currency explicitly (or uses the currency-aware hook) instead of
 * hardcoding USD.
 */
export function formatCurrency(
  amount: number,
  currency: string = 'USD',
  locale: string = 'en-US',
  options: { maximumFractionDigits?: number; minimumFractionDigits?: number } = {}
): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    ...options,
  }).format(amount);
}

/**
 * Maps a practice country code (ISO 3166-1 alpha-2, as carried on the auth
 * user's `practiceCountry`) to the currency used for practice money display.
 * Unknown/missing countries default to USD.
 */
export function currencyForCountry(country?: string | null): string {
  switch ((country ?? '').trim().toUpperCase()) {
    case 'IN':
      return 'INR';
    case 'GB':
      return 'GBP';
    case 'CA':
      return 'CAD';
    case 'AU':
      return 'AUD';
    case 'US':
    default:
      return 'USD';
  }
}

/**
 * Formats a date using date-fns
 */
export function formatDate(
  date: Date | string,
  formatStr: string = 'MMMM d, yyyy'
): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;

  // Token-based formatter supporting the date-fns-style patterns used in
  // this app. Previously any format other than the literal 'yyyy-MM-dd'
  // silently fell back to 'MMMM d, yyyy'.
  const monthsLong = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  const monthsShort = monthsLong.map((m) => m.slice(0, 3));

  const pad2 = (n: number) => String(n).padStart(2, '0');
  const tokens: Record<string, string> = {
    yyyy: String(dateObj.getFullYear()),
    MM: pad2(dateObj.getMonth() + 1),
    MMMM: monthsLong[dateObj.getMonth()],
    MMM: monthsShort[dateObj.getMonth()],
    dd: pad2(dateObj.getDate()),
    d: String(dateObj.getDate()),
    HH: pad2(dateObj.getHours()),
    mm: pad2(dateObj.getMinutes()),
  };

  return formatStr.replace(/yyyy|MMMM|MMM|MM|dd|d|HH|mm/g, (t) => tokens[t] ?? t);
}

/**
 * Formats a phone number
 */
export function formatPhoneNumber(phone: string): string {
  // Remove all non-digit characters
  const cleaned = phone.replace(/\D/g, '');
  
  // Check if it's a valid US phone number
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  
  // Check if it has country code
  if (cleaned.length === 11 && cleaned[0] === '1') {
    return `+1 (${cleaned.slice(1, 4)}) ${cleaned.slice(4, 7)}-${cleaned.slice(7)}`;
  }
  
  // Return original if format is unknown
  return phone;
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  
  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };
    
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;
  
  return function executedFunction(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Deep clone an object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Check if value is empty (null, undefined, empty string, empty array, empty object)
 */
export function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
}

/**
 * Capitalize first letter of string
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Generate a random ID
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Sleep/delay function
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Truncate string with ellipsis
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

/**
 * Get initials from a full name string
 */
export function getInitials(name: string): string {
  if (!name || typeof name !== 'string') return '';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}

/**
 * Validate email address
 */
export function validateEmail(email: string): boolean {
  if (!email || typeof email !== 'string') return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * Capitalize words in a string
 */
export function capitalizeWords(str: string): string {
  if (!str || typeof str !== 'string') return '';
  return str
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Convert string to URL-friendly slug
 */
export function slugify(str: string): string {
  if (!str || typeof str !== 'string') return '';
  return str
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

/**
 * Parse JWT token payload
 */
export function parseJwt(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join(''),
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/**
 * Check if string is a valid UUID
 */
export function isValidUUID(str: string): boolean {
  if (!str || typeof str !== 'string') return false;
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
}

/**
 * Extract error message from various error types
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'An unknown error occurred';
}

/**
 * Retry an async function with exponential backoff
 */
export function retry<T>(
  fn: () => Promise<T>,
  options: { maxAttempts?: number; delay?: number } = {},
): Promise<T> {
  const { maxAttempts = 3, delay = 1000 } = options;

  return new Promise((resolve, reject) => {
    const attempt = async (currentAttempt: number) => {
      try {
        const result = await fn();
        resolve(result);
      } catch (error) {
        if (currentAttempt >= maxAttempts) {
          reject(error);
        } else {
          // Exponential backoff (delay, 2*delay, 4*delay, ...) as documented
          // in the JSDoc — the previous `delay * currentAttempt` was linear.
          setTimeout(
            () => attempt(currentAttempt + 1),
            delay * Math.pow(2, currentAttempt - 1)
          );
        }
      }
    };
    attempt(1);
  });
}
