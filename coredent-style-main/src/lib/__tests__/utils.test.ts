import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  cn,
  toURLSearchParams,
  formatCurrency,
  formatDate,
  formatPhoneNumber,
  debounce,
  throttle,
  deepClone,
  isEmpty,
  capitalize,
  generateId,
  sleep,
  truncate,
  getInitials,
  validateEmail,
  truncateText,
  capitalizeWords,
  slugify,
  parseJwt,
  isValidUUID,
  getErrorMessage,
  retry,
} from '../utils';

describe('utils', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('formats, normalizes, and validates common values', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(Math, 'random').mockReturnValue(0.123456789);

    expect(cn('a', undefined, 'c')).toContain('a');
    expect(toURLSearchParams({ a: '1', b: undefined, c: null, d: '', e: ['x', 'y'], f: 2 }).toString()).toBe('a=1&e=x%2Cy&f=2');
    expect(formatCurrency(1234.5)).toBe('$1,234.50');
    expect(formatDate('2026-06-27')).toBe('June 27, 2026');
    expect(formatDate('2026-06-27', 'yyyy-MM-dd')).toBe('2026-06-27');
    expect(formatPhoneNumber('555-123-4567')).toBe('(555) 123-4567');
    expect(formatPhoneNumber('1 (555) 123-4567')).toBe('+1 (555) 123-4567');
    expect(formatPhoneNumber('abc')).toBe('abc');
    expect(deepClone({ a: { b: 1 } })).toEqual({ a: { b: 1 } });
    expect(isEmpty(null)).toBe(true);
    expect(isEmpty('   ')).toBe(true);
    expect(isEmpty([])).toBe(true);
    expect(isEmpty({})).toBe(true);
    expect(isEmpty('x')).toBe(false);
    expect(capitalize('maya')).toBe('Maya');
    expect(generateId('task')).toMatch(/^task-1700000000000-/);
    expect(truncate('hello world', 5)).toBe('hello...');
    expect(getInitials('Maya Patel')).toBe('MP');
    expect(getInitials('maya')).toBe('M');
    expect(validateEmail('doctor@example.com')).toBe(true);
    expect(validateEmail('bad')).toBe(false);
    expect(truncateText('abcdef', 3)).toBe('abc...');
    expect(capitalizeWords('hello world')).toBe('Hello World');
    expect(slugify('Hello, World!')).toBe('hello-world');
    expect(isValidUUID('123e4567-e89b-12d3-a456-426614174000')).toBe(true);
    expect(isValidUUID('nope')).toBe(false);
    expect(getErrorMessage(new Error('boom'))).toBe('boom');
    expect(getErrorMessage('fail')).toBe('fail');
    expect(getErrorMessage({})).toBe('An unknown error occurred');
    expect(parseJwt('bad.token')).toBeNull();
    expect(parseJwt('')).toBeNull();
  });

  it('supports async helpers and control flow helpers', async () => {
    const debounced = vi.fn();
    const throttled = vi.fn();

    const debouncedFn = debounce(debounced, 100);
    debouncedFn('a');
    debouncedFn('b');
    vi.advanceTimersByTime(99);
    expect(debounced).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(debounced).toHaveBeenCalledTimes(1);
    expect(debounced).toHaveBeenCalledWith('b');

    const throttledFn = throttle(throttled, 100);
    throttledFn('first');
    throttledFn('second');
    expect(throttled).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(100);
    throttledFn('third');
    expect(throttled).toHaveBeenCalledTimes(2);

    const sleepPromise = sleep(50);
    vi.advanceTimersByTime(50);
    await expect(sleepPromise).resolves.toBeUndefined();

    let attempts = 0;
    const retried = retry(
      async () => {
        attempts += 1;
        if (attempts < 3) throw new Error(`attempt ${attempts}`);
        return 'ok';
      },
      { maxAttempts: 3, delay: 10 },
    );

    await vi.runAllTimersAsync();
    await expect(retried).resolves.toBe('ok');
  });
});
