// CSRF Protection
// Implements CSRF token management for API requests

const CSRF_TOKEN_KEY = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

/**
 * Gets the current CSRF token from sessionStorage
 * @returns CSRF token string
 */
export function getCsrfToken(): string | null {
  return sessionStorage.getItem(CSRF_TOKEN_KEY);
}

/**
 * Sets a new CSRF token
 * @param token - Token string to set
 */
export function setCsrfToken(token: string): void {
  sessionStorage.setItem(CSRF_TOKEN_KEY, token);
}

/**
 * Clears the CSRF token
 */
export function clearCsrfToken(): void {
  sessionStorage.removeItem(CSRF_TOKEN_KEY);
}

/**
 * Gets CSRF header object for fetch requests
 * @returns Object with CSRF header
 */
export function getCsrfHeader(): Record<string, string> {
  const token = getCsrfToken();
  if (!token) {
    return {};
  }
  return {
    [CSRF_HEADER_NAME]: token,
  };
}

/**
 * Validates CSRF token from response
 * @param responseToken - Token from API response
 * @returns True if token is valid
 */
export function validateCsrfToken(responseToken: string): boolean {
  const currentToken = getCsrfToken();
  return currentToken === responseToken;
}

/**
 * Refreshes CSRF token (call after login)
 */
export function refreshCsrfToken(token: string): void {
  setCsrfToken(token);
}

/**
 * Gets the CSRF header name
 * @returns Header name string
 */
export function getCsrfHeaderName(): string {
  return CSRF_HEADER_NAME;
}
