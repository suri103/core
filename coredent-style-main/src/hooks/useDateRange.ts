import { useState, useCallback, useMemo } from 'react';
import { subDays, subMonths, startOfMonth, endOfMonth } from 'date-fns';
import type { DateRange } from '@/types/reports';

export type PresetRange = 'last7days' | 'last30days' | 'thisMonth' | 'lastMonth' | 'last3months' | 'custom';

export const PRESET_RANGES: { value: PresetRange; label: string }[] = [
  { value: 'last7days', label: 'Last 7 Days' },
  { value: 'last30days', label: 'Last 30 Days' },
  { value: 'thisMonth', label: 'This Month' },
  { value: 'lastMonth', label: 'Last Month' },
  { value: 'last3months', label: 'Last 3 Months' },
];

export function getDateRangeFromPreset(preset: PresetRange): DateRange {
  const today = new Date();
  switch (preset) {
    case 'last7days':
      return { from: subDays(today, 7), to: today };
    case 'last30days':
      return { from: subDays(today, 30), to: today };
    case 'thisMonth':
      return { from: startOfMonth(today), to: today };
    case 'lastMonth': {
      const lastMonth = subMonths(today, 1);
      return { from: startOfMonth(lastMonth), to: endOfMonth(lastMonth) };
    }
    case 'last3months':
      return { from: subMonths(today, 3), to: today };
    default:
      return { from: subDays(today, 30), to: today };
  }
}

/**
 * Hook for managing date range selection and presets.
 */
export function useDateRange(initialPreset: PresetRange = 'last30days') {
  const [selectedPreset, setSelectedPreset] = useState<PresetRange>(initialPreset);
  const [dateRange, setDateRange] = useState<DateRange>(() => getDateRangeFromPreset(initialPreset));

  const handlePresetChange = useCallback((preset: PresetRange) => {
    setSelectedPreset(preset);
    if (preset !== 'custom') {
      setDateRange(getDateRangeFromPreset(preset));
    }
  }, []);

  const setCustomRange = useCallback((range: DateRange) => {
    setDateRange(range);
    setSelectedPreset('custom');
  }, []);

  // Memoize dateRange to prevent unnecessary re-renders
  const memoizedDateRange = useMemo(() => dateRange, [dateRange]);

  return {
    dateRange: memoizedDateRange,
    selectedPreset,
    handlePresetChange,
    setCustomRange,
    PRESET_RANGES,
  };
}
