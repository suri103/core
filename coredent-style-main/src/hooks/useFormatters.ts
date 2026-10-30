/**
 * useFormatters Hook
 * Provides formatting utilities for common data types
 */

import { useCallback } from 'react';
import { formatCurrency as formatCurrencyUtil } from '@/lib/utils';

interface UseFormattersResult {
  formatCurrency: (amount: number) => string;
  formatAppointmentType: (type: string) => string;
  formatDate: (date: Date | string) => string;
  formatTime: (date: Date | string) => string;
}

/**
 * Hook to get formatting utilities
 *
 * @param currency - ISO 4217 code used for money formatting (default 'USD')
 *
 * @returns Object with formatting functions
 *
 * @example
 * const { formatCurrency, formatAppointmentType } = useFormatters('INR');
 * const price = formatCurrency(100);
 * const type = formatAppointmentType('root_canal');
 */
export function useFormatters(currency: string = 'USD'): UseFormattersResult {
  const formatCurrency = useCallback((amount: number): string => {
    return formatCurrencyUtil(amount, currency, 'en-US', { maximumFractionDigits: 0 });
  }, [currency]);

  const formatAppointmentType = useCallback((value: string): string => {
    if (!value) return '';
    return value
      .split('_')
      .map(word => (word?.charAt(0) || '?').toUpperCase() + (word?.slice(1) || ''))
      .join(' ');
  }, []);

  const formatDate = useCallback((date: Date | string): string => {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }, []);

  const formatTime = useCallback((date: Date | string): string => {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  }, []);

  return {
    formatCurrency,
    formatAppointmentType,
    formatDate,
    formatTime,
  };
}
