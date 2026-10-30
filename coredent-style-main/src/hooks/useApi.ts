import { useState, useCallback, useEffect } from 'react';
import { logger } from '@/lib/logger';
import { apiClient } from '@/services/api';

interface UseApiResult<T> {
  loading: boolean;
  data: T | null;
  error: Error | null;
  refetch: () => void;
}

export function useApi<T = unknown>(endpoint: string): UseApiResult<T> {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<T>(endpoint);
      if (response.success && response.data !== undefined) {
        setData(response.data);
      } else {
        throw new Error(response.error?.message ?? 'No response data was returned.');
      }
    } catch (err) {
      const requestError = err instanceof Error ? err : new Error(String(err));
      setError(requestError);
      logger.error(`useApi request failed: ${endpoint}`, requestError);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData();
  }, [fetchData, fetchTrigger]);

  const refetch = useCallback(() => {
    setFetchTrigger((prev) => prev + 1);
  }, []);

  return { loading, data, error, refetch };
}
