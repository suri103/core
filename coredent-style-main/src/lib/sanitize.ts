/**
 * Input Sanitization Utilities
 * Security utilities for XSS prevention and data sanitization
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content to prevent XSS attacks
 * @param html - Raw HTML string to sanitize
 * @param options - DOMPurify configuration options
 * @returns Sanitized HTML string
 */
export function sanitizeHtml(
  html: string,
  options?: Parameters<typeof DOMPurify.sanitize>[1]
): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ...options,
  }) as string;
}

/**
 * Sanitize text content (escape HTML entities)
 * @param text - Raw text to sanitize
 * @returns Sanitized text safe for display
 */
export function sanitizeText(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Sanitize URL to prevent javascript: protocol attacks
 * @param url - URL to sanitize
 * @returns Sanitized URL or empty string if invalid
 */
export function sanitizeUrl(url: string): string {
  if (!url) return '';
  
  try {
    const parsed = new URL(url);
    const validProtocols = ['http:', 'https:', 'mailto:', 'tel:'];
    
    if (validProtocols.includes(parsed.protocol)) {
      return parsed.href;
    }
  } catch {
    // If URL parsing fails, check if it's a relative URL
    if (url.startsWith('/') || url.startsWith('#')) {
      return url;
    }
  }
  
  return '';
}

/**
 * Sanitize patient notes and clinical data
 * @param content - Raw content from patient notes
 * @returns Sanitized content safe for display
 */
export function sanitizePatientNote(content: string): string {
  return sanitizeHtml(content, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'],
    ALLOWED_ATTR: [],
  });
}

/**
 * Sanitize JSON data recursively
 * @param data - Object with potentially unsafe string values
 * @returns Object with sanitized string values
 */
export function sanitizeJson(data: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === 'string') {
      result[key] = sanitizeText(value);
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      result[key] = sanitizeJson(value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  }
  
  return result;
}

/**
 * Validate and sanitize email address
 * @param email - Email address to validate
 * @returns Sanitized email or null if invalid
 */
export function sanitizeEmail(email: string): string | null {
  const trimmed = email.trim().toLowerCase();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  
  if (emailRegex.test(trimmed)) {
    return trimmed;
  }
  
  return null;
}

/**
 * Sanitize phone number (remove non-numeric characters except +)
 * @param phone - Phone number to sanitize
 * @returns Sanitized phone number
 */
export function sanitizePhone(phone: string): string {
  return phone.replace(/[^\d+]/g, '');
}

/**
 * Create a sanitized React dangerouslySetInnerHTML object
 * @param html - Raw HTML string
 * @returns Object suitable for dangerouslySetInnerHTML
 */
export function createSanitizedHtml(html: string): { __html: string } {
  return { __html: sanitizeHtml(html) };
}