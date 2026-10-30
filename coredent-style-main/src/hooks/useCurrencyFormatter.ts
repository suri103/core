// ============================================
// CoreDent PMS - Currency-aware money formatting
// ============================================
// Multi-country practices must not see a hardcoded "$". The practice's
// configured currency (exposed on /auth/me) wins; country-derived currency
// is the fallback; USD is the final default.

import { useCallback, useMemo } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { formatCurrency, currencyForCountry } from '@/lib/utils';

interface UseCurrencyFormatterResult {
  /** ISO 4217 code currently used for display (e.g. 'USD', 'INR'). */
  currency: string;
  /** Formats an amount in the practice currency. */
  formatCurrency: (amount: number) => string;
}

export function useCurrencyFormatter(
  options: { maximumFractionDigits?: number; minimumFractionDigits?: number } = {}
): UseCurrencyFormatterResult {
  const { user } = useAuth();
  // Destructure to primitives so the callback deps stay stable regardless of
  // whether callers pass an inline object literal (L-04).
  const { maximumFractionDigits, minimumFractionDigits } = options;

  const currency = useMemo(
    () => user?.practiceCurrency || currencyForCountry(user?.practiceCountry),
    [user?.practiceCurrency, user?.practiceCountry]
  );

  const format = useCallback(
    (amount: number) =>
      formatCurrency(amount, currency, 'en-US', {
        maximumFractionDigits,
        minimumFractionDigits,
      }),
    [currency, maximumFractionDigits, minimumFractionDigits]
  );

  return { currency, formatCurrency: format };
}
