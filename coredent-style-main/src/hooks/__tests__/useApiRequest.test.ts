import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useApiRequest } from '../useApiRequest';

const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

describe('useApiRequest hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles successful API request', async () => {
    const mockApiFunc = vi.fn().mockResolvedValueOnce({ success: true, data: 'test-data' });
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useApiRequest(mockApiFunc, {
      successMessage: 'Loaded successfully',
      onSuccess,
    }));

    let response;
    await act(async () => {
      response = await result.current.execute('arg1');
    });

    expect(mockApiFunc).toHaveBeenCalledWith('arg1');
    expect(result.current.data).toBe('test-data');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(response).toBe('test-data');
    expect(mockToast).toHaveBeenCalledWith({
      title: 'Success',
      description: 'Loaded successfully',
    });
    expect(onSuccess).toHaveBeenCalledWith('test-data');
  });

  it('handles API error response', async () => {
    const mockApiFunc = vi.fn().mockResolvedValueOnce({
      success: false,
      error: { message: 'Resource not found' },
    });
    const onError = vi.fn();
    const { result } = renderHook(() => useApiRequest(mockApiFunc, {
      onError,
    }));

    let response;
    await act(async () => {
      response = await result.current.execute();
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe('Resource not found');
    expect(response).toBeNull();
    expect(mockToast).toHaveBeenCalledWith({
      variant: 'destructive',
      title: 'Error',
      description: 'Resource not found',
    });
    expect(onError).toHaveBeenCalledWith({ message: 'Resource not found' });
  });

  it('handles API error response with fallback messages', async () => {
    const mockApiFunc = vi.fn().mockResolvedValueOnce({
      success: false,
    });
    const { result } = renderHook(() => useApiRequest(mockApiFunc, {
      errorMessage: 'Custom error message',
    }));

    await act(async () => {
      await result.current.execute();
    });
    expect(result.current.error).toBe('Custom error message');

    // Test absolute fallback 'An error occurred'
    const mockApiFunc2 = vi.fn().mockResolvedValueOnce({ success: false });
    const { result: result2 } = renderHook(() => useApiRequest(mockApiFunc2));
    await act(async () => {
      await result2.current.execute();
    });
    expect(result2.current.error).toBe('An error occurred');
  });

  it('handles successful API request with missing data fallback', async () => {
    const mockApiFunc = vi.fn().mockResolvedValueOnce({ success: true });
    const { result } = renderHook(() => useApiRequest(mockApiFunc));

    let response;
    await act(async () => {
      response = await result.current.execute();
    });
    expect(result.current.data).toBeNull();
    expect(response).toBeNull();
  });

  it('handles network / unexpected errors in catch block', async () => {
    const mockApiFunc = vi.fn().mockRejectedValueOnce(new Error('Connection timed out'));
    const onError = vi.fn();
    const { result } = renderHook(() => useApiRequest(mockApiFunc, {
      errorMessage: 'Failed to connect to server',
      onError,
    }));

    let response;
    await act(async () => {
      response = await result.current.execute();
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe('Failed to connect to server');
    expect(response).toBeNull();
    expect(mockToast).toHaveBeenCalledWith({
      variant: 'destructive',
      title: 'Error',
      description: 'Failed to connect to server',
    });
    expect(onError).toHaveBeenCalled();
  });

  it('handles network / unexpected errors with default fallback message', async () => {
    const mockApiFunc = vi.fn().mockRejectedValueOnce(new Error('Generic network error'));
    const { result } = renderHook(() => useApiRequest(mockApiFunc));

    await act(async () => {
      await result.current.execute();
    });
    expect(result.current.error).toBe('Network error occurred');
  });
});
