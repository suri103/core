import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  retryWithBackoff,
  apiCircuitBreaker,
  withFallback,
  withTimeout,
  debounceAsync,
  throttleAsync,
  batchOperations,
} from '../errorRecovery';

describe('retryWithBackoff', () => {
  beforeEach(() => {
    apiCircuitBreaker.reset();
  });

  it('returns the result when the operation succeeds first try', async () => {
    const op = vi.fn().mockResolvedValue('ok');
    const result = await retryWithBackoff(op, { initialDelay: 1, maxDelay: 1 });
    expect(result).toBe('ok');
    expect(op).toHaveBeenCalledOnce();
  });

  it('retries on a retryable error and eventually succeeds', async () => {
    const op = vi
      .fn()
      .mockRejectedValueOnce(new Error('NETWORK_ERROR occurred'))
      .mockResolvedValueOnce('ok');

    const onRetry = vi.fn();
    const result = await retryWithBackoff(op, {
      initialDelay: 1,
      maxDelay: 1,
      onRetry,
    });
    expect(result).toBe('ok');
    expect(op).toHaveBeenCalledTimes(2);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('throws after maxAttempts when the error persists', async () => {
    const op = vi.fn().mockRejectedValue(new Error('NETWORK_ERROR'));
    await expect(
      retryWithBackoff(op, { maxAttempts: 3, initialDelay: 1, maxDelay: 1 }),
    ).rejects.toThrow('NETWORK_ERROR');
    expect(op).toHaveBeenCalledTimes(3);
  });

  it('does not retry on a non-retryable error', async () => {
    const op = vi.fn().mockRejectedValue(new Error('BAD_REQUEST'));
    await expect(
      retryWithBackoff(op, { maxAttempts: 3, initialDelay: 1, maxDelay: 1 }),
    ).rejects.toThrow('BAD_REQUEST');
    expect(op).toHaveBeenCalledOnce();
  });
});

describe('withFallback', () => {
  it('returns the primary result on success', async () => {
    const result = await withFallback(
      async () => 'primary',
      () => 'fallback',
    );
    expect(result).toBe('primary');
  });

  it('returns the fallback on primary failure', async () => {
    const result = await withFallback(
      async () => {
        throw new Error('boom');
      },
      () => 'fallback',
    );
    expect(result).toBe('fallback');
  });

  it('accepts an async fallback', async () => {
    const result = await withFallback(
      async () => {
        throw new Error('boom');
      },
      async () => 'async-fallback',
    );
    expect(result).toBe('async-fallback');
  });
});

describe('withTimeout', () => {
  it('resolves with the promise value when fast enough', async () => {
    const result = await withTimeout(Promise.resolve('ok'), 100);
    expect(result).toBe('ok');
  });

  it('rejects with a timeout error when too slow', async () => {
    const slow = new Promise((resolve) => setTimeout(() => resolve('late'), 100));
    await expect(withTimeout(slow, 5, 'too slow')).rejects.toThrow('too slow');
  });
});

describe('debounceAsync', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('coalesces rapid calls into a single trailing invocation', async () => {
    const fn = vi.fn(async (x: number) => x * 2);
    const debounced = debounceAsync(fn, 100);

    const p1 = debounced(1);
    const p2 = debounced(2);
    const p3 = debounced(3);

    await vi.advanceTimersByTimeAsync(100);
    const result = await p3;
    expect(result).toBe(6);
    expect(fn).toHaveBeenCalledOnce();
    expect(fn).toHaveBeenCalledWith(3);
    // Resolve the early promises (they never resolve, so we don't await them)
    p1.catch(() => undefined);
    p2.catch(() => undefined);
  });
});

describe('throttleAsync', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('only invokes the first call during the throttle window', async () => {
    const fn = vi.fn(async (x: number) => x);
    const throttled = throttleAsync(fn, 100);

    const p1 = throttled(1);
    await vi.advanceTimersByTimeAsync(0);
    const r1 = await p1;
    expect(r1).toBe(1);

    const p2 = throttled(2);
    const r2 = await p2;
    expect(r2).toBe(1);
    expect(fn).toHaveBeenCalledOnce();
  });
});

describe('batchOperations', () => {
  it('returns the combined results in order', async () => {
    const op = async (n: number) => n * 10;
    const result = await batchOperations([1, 2, 3, 4, 5], op, 2, 1);
    expect(result).toEqual([10, 20, 30, 40, 50]);
  });

  it('handles an empty input', async () => {
    const result = await batchOperations([], async (n: number) => n, 10, 1);
    expect(result).toEqual([]);
  });

  it('preserves order even when the operation is async', async () => {
    const op = async (n: number) => {
      await new Promise((r) => setTimeout(r, Math.random() * 5));
      return n;
    };
    const result = await batchOperations([1, 2, 3], op, 5, 1);
    expect(result).toEqual([1, 2, 3]);
  });
});

describe('apiCircuitBreaker', () => {
  it('starts in the closed state', () => {
    apiCircuitBreaker.reset();
    expect(apiCircuitBreaker.getState()).toBe('closed');
  });

  it('opens after the threshold of failures', async () => {
    apiCircuitBreaker.reset();
    const op = async () => {
      throw new Error('boom');
    };
    for (let i = 0; i < 5; i++) {
      await expect(apiCircuitBreaker.execute(op)).rejects.toThrow('boom');
    }
    expect(apiCircuitBreaker.getState()).toBe('open');
  });

  it('rejects requests immediately when the breaker is open', async () => {
    apiCircuitBreaker.reset();
    const op = async () => {
      throw new Error('boom');
    };
    for (let i = 0; i < 5; i++) {
      await expect(apiCircuitBreaker.execute(op)).rejects.toThrow('boom');
    }
    // Subsequent calls fail fast
    await expect(apiCircuitBreaker.execute(op)).rejects.toThrow(/Circuit breaker is open/);
  });

  it('resets the breaker manually', async () => {
    apiCircuitBreaker.reset();
    const op = async () => {
      throw new Error('boom');
    };
    for (let i = 0; i < 5; i++) {
      await expect(apiCircuitBreaker.execute(op)).rejects.toThrow();
    }
    expect(apiCircuitBreaker.getState()).toBe('open');
    apiCircuitBreaker.reset();
    expect(apiCircuitBreaker.getState()).toBe('closed');
  });
});
