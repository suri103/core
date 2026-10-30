import { useState, useCallback, useRef, useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';
import type { ApiResponse } from '@/types/api';
import { logger } from '@/lib/logger';

interface UseApiRequestOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: unknown) => void;
  successMessage?: string;
  errorMessage?: string;
}

/**
 * Standard hook for managing API requests with loading, error, and toast notifications.
 *
 * `apiFunc` and `options` are read through refs so `execute` keeps a stable
 * identity across renders. Callers frequently pass inline arrow functions and
 * object literals; depending on those identities directly made `execute` (and
 * therefore any effect depending on it) change on every render, causing an
 * infinite refetch loop.
 */
export function useApiRequest<T>(
  apiFunc: (...args: unknown[]) => Promise<ApiResponse<T>>,
  options: UseApiRequestOptions<T> = {}
) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const apiFuncRef = useRef(apiFunc);
  const optionsRef = useRef(options);
  useEffect(() => {
    apiFuncRef.current = apiFunc;
    optionsRef.current = options;
  });

  const execute = useCallback(
    async (...args: unknown[]) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiFuncRef.current(...args);

        if (response.success) {
          setData(response.data ?? null);
          if (optionsRef.current.successMessage) {
            toast({
              title: 'Success',
              description: optionsRef.current.successMessage,
            });
          }
          optionsRef.current.onSuccess?.(response.data as T);
          return response.data ?? null;
        } else {
          const message = response.error?.message || optionsRef.current.errorMessage || 'An error occurred';
          setError(message);
          toast({
            variant: 'destructive',
            title: 'Error',
            description: message,
          });
          optionsRef.current.onError?.(response.error);
          return null;
        }
      } catch (err) {
        const message = optionsRef.current.errorMessage || 'Network error occurred';
        setError(message);
        logger.error('API Request hook failed', err as Error);
        toast({
          variant: 'destructive',
          title: 'Error',
          description: message,
        });
        optionsRef.current.onError?.(err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast]
  );

  return {
    data,
    setData,
    isLoading,
    error,
    execute,
  };
}
