// ============================================
// CoreDent PMS - Test Setup
// Global test configuration and mocks
// ============================================

import '@testing-library/jest-dom';
import { vi, beforeAll, beforeEach, afterEach, afterAll } from 'vitest';
import { cleanup } from '@testing-library/react';
import { server } from './mocks/server';

// Ensure API requests use relative paths so MSW handlers match
vi.stubEnv('VITE_API_BASE_URL', '/api/v1');

// Mock virtual:pwa-register/react for testing
vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: vi.fn(() => ({
    needRefresh: [false, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: vi.fn(),
  })),
}));

// ============================================
// MSW Server Setup
// ============================================
// Silence expected logger/React/test noise while still allowing spies to assert calls.
const muteConsole = () => {
  vi.spyOn(console, 'debug').mockImplementation(() => {});
  vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'log').mockImplementation(() => {});
};

beforeEach(() => {
  muteConsole();
});

// Start server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));

// Reset handlers after each test
afterEach(() => server.resetHandlers());

// Clean up after all tests
afterAll(() => server.close());

// ============================================
// DOM Cleanup (React Testing Library)
// ============================================

// Unmount any rendered components after each test to avoid DOM/state leaks
afterEach(() => cleanup());

// ============================================
// Global Mocks
// ============================================

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Use real constructor-shaped test doubles. UI libraries instantiate these
// browser APIs with `new`, which arrow-function mock implementations do not
// support.
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

global.ResizeObserver = MockResizeObserver as typeof ResizeObserver;

class MockIntersectionObserver {
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds = [];
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn(() => []);
}

global.IntersectionObserver =
  MockIntersectionObserver as typeof IntersectionObserver;

// Mock scrollTo
window.scrollTo = vi.fn();

// jsdom does not implement these Element methods; Radix UI relies on them.
window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.HTMLElement.prototype.hasPointerCapture = vi.fn(() => false);
window.HTMLElement.prototype.releasePointerCapture = vi.fn();
window.HTMLElement.prototype.setPointerCapture = vi.fn();

// Mock sessionStorage
const mockSessionStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn(function (this: { length: number }, key: string, value: string) {
      store[key] = value;
      this.length = Object.keys(store).length;
    }),
    removeItem: vi.fn(function (this: { length: number }, key: string) {
      delete store[key];
      this.length = Object.keys(store).length;
    }),
    clear: vi.fn(function (this: { length: number }) {
      store = {};
      this.length = 0;
    }),
    // Storage interface members used by cache eviction logic.
    // `length` is a plain writable property (kept in sync below) because some
    // tests Object.assign their own mock onto the storage object.
    length: 0,
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
  };
})();

Object.defineProperty(window, 'sessionStorage', {
  value: mockSessionStorage,
});

// Mock localStorage
const mockLocalStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn(function (this: { length: number }, key: string, value: string) {
      store[key] = value;
      this.length = Object.keys(store).length;
    }),
    removeItem: vi.fn(function (this: { length: number }, key: string) {
      delete store[key];
      this.length = Object.keys(store).length;
    }),
    clear: vi.fn(function (this: { length: number }) {
      store = {};
      this.length = 0;
    }),
    // Storage interface members used by cache eviction logic.
    // `length` is a plain writable property (kept in sync below) because some
    // tests Object.assign their own mock onto the storage object.
    length: 0,
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// ============================================
// Custom Matchers
// ============================================

expect.extend({
  toBeValidDate(received: unknown) {
    const pass = received instanceof Date && !isNaN(received.getTime());
    return {
      pass,
      message: () =>
        pass
          ? `expected ${received} not to be a valid date`
          : `expected ${received} to be a valid date`,
    };
  },
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    return {
      pass,
      message: () =>
        pass
          ? `expected ${received} not to be within range ${floor} - ${ceiling}`
          : `expected ${received} to be within range ${floor} - ${ceiling}`,
    };
  },
});
