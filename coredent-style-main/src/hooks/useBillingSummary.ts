/**
 * useBillingSummary Hook
 * Fetches and manages billing summary data
 */

import { useQuery } from '@tanstack/react-query';
import { billingApi } from '@/services/billingApi';
import type { BillingSummary } from '@/types/billing';

interface UseBillingSummaryOptions {
  enabled?: boolean;
}

interface UseBillingSummaryResult {
  billingSummary: BillingSummary | null;
  pendingCount: number;
  pendingAmount: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook to fetch billing summary
 * 
 * @param options - Configuration options
 * @returns Billing summary data
 * 
 * @example
 * const { billingSummary, pendingCount } = useBillingSummary();
 */
export function useBillingSummary(
  options: UseBillingSummaryOptions = {}
): UseBillingSummaryResult {
  const { enabled = true } = options;

  const { data: billingSummary, isLoading, isError, error } = useQuery({
    queryKey: ['dashboard', 'billing-summary'],
    queryFn: () => billingApi.getSummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled,
  });

  const pendingCount = billingSummary?.pendingCount ?? 0;
  const pendingAmount = billingSummary?.pendingAmount ?? 0;

  return {
    billingSummary: billingSummary ?? null,
    pendingCount,
    pendingAmount,
    isLoading,
    isError,
    error: error instanceof Error ? error : null,
  };
}
