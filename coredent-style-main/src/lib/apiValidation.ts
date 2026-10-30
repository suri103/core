// API Response Validation
// Validates API responses against expected schemas

import { z } from 'zod';
import { logger } from './logger';

/**
 * Describe the *shape* of a payload without its values. Validation failures
 * used to log the full response body, which can contain patient, billing, or
 * clinical PHI; only the structural fingerprint is safe for client logs.
 */
function describeShape(value: unknown, depth = 0): string {
  if (value === null || value === undefined) return String(value);
  if (Array.isArray(value)) {
    if (depth > 3) return 'array(…)';
    const first = value.length > 0 ? describeShape(value[0], depth + 1) : 'empty';
    return `array(${value.length})<${first}>`;
  }
  if (typeof value === 'object') {
    if (depth > 3) return 'object(…)';
    const keys = Object.keys(value as Record<string, unknown>)
      .slice(0, 25)
      .sort()
      .join(',');
    return `{${keys}}`;
  }
  return typeof value;
}

/**
 * Validates API response data against a Zod schema
 * @param data - The data to validate
 * @param schema - Zod schema to validate against
 * @param endpoint - API endpoint for logging
 * @returns Validated data or null if validation fails
 */
export function validateApiResponse<T>(
  data: unknown,
  schema: z.ZodSchema<T>,
  endpoint: string
): T | null {
  try {
    return schema.parse(data);
  } catch (error) {
    // M-16 FIX: log a shape fingerprint, never the response body (PHI).
    logger.error(`API response validation failed for ${endpoint}`, error as Error, {
      endpoint,
      receivedShape: describeShape(data),
    });
    return null;
  }
}

/**
 * Validates API response data and throws on failure
 * @param data - The data to validate
 * @param schema - Zod schema to validate against
 * @param endpoint - API endpoint for logging
 * @returns Validated data
 * @throws Error if validation fails
 */
export function validateApiResponseStrict<T>(
  data: unknown,
  schema: z.ZodSchema<T>,
  endpoint: string
): T {
  try {
    return schema.parse(data);
  } catch (error) {
    logger.error(`API response validation failed for ${endpoint}`, error as Error, {
      endpoint,
      receivedShape: describeShape(data),
    });
    throw new Error(`Invalid API response from ${endpoint}`);
  }
}

/**
 * Sanitizes user input to prevent XSS attacks
 * @param input - User input string
 * @returns Sanitized string
 */
export function sanitizeInput(input: string): string {
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Validates email format
 * @param email - Email string to validate
 * @returns True if valid email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validates phone number format (US)
 * @param phone - Phone number string
 * @returns True if valid phone format
 */
export function isValidPhone(phone: string): boolean {
  const phoneRegex = /^\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$/;
  return phoneRegex.test(phone);
}

/**
 * Validates URL format
 * @param url - URL string to validate
 * @returns True if valid URL format
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Checks if a value is a safe integer
 * @param value - Value to check
 * @returns True if safe integer
 */
export function isSafeInteger(value: unknown): boolean {
  return typeof value === 'number' && Number.isSafeInteger(value);
}

/**
 * Validates date string format (ISO 8601)
 * @param dateString - Date string to validate
 * @returns True if valid ISO date format
 */
export function isValidISODate(dateString: string): boolean {
  const date = new Date(dateString);
  return date instanceof Date && !isNaN(date.getTime());
}
