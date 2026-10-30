import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDateRange, getDateRangeFromPreset } from '../useDateRange';
import { subMonths, endOfMonth } from 'date-fns';

describe('useDateRange hook & helper', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-28T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });
  describe('getDateRangeFromPreset', () => {
    it('returns correct range for last7days', () => {
      const range = getDateRangeFromPreset('last7days');
      expect(range.to).toBeInstanceOf(Date);
      expect(range.from).toBeInstanceOf(Date);
    });

    it('returns correct range for last30days', () => {
      const range = getDateRangeFromPreset('last30days');
      expect(range.to).toBeInstanceOf(Date);
      expect(range.from).toBeInstanceOf(Date);
    });

    it('returns correct range for thisMonth', () => {
      const range = getDateRangeFromPreset('thisMonth');
      expect(range.to).toBeInstanceOf(Date);
      expect(range.from).toBeInstanceOf(Date);
    });

    it('returns correct range for lastMonth', () => {
      const range = getDateRangeFromPreset('lastMonth');
      const today = new Date();
      const lastMonth = subMonths(today, 1);
      expect(range.from.getDate()).toBe(1);
      expect(range.to.getDate()).toBe(endOfMonth(lastMonth).getDate());
    });

    it('returns correct range for last3months', () => {
      const range = getDateRangeFromPreset('last3months');
      expect(range.to).toBeInstanceOf(Date);
      expect(range.from).toBeInstanceOf(Date);
    });

    it('falls back to last30days for invalid preset', () => {
      const range = getDateRangeFromPreset('invalid' as any);
      expect(range.to).toBeInstanceOf(Date);
      expect(range.from).toBeInstanceOf(Date);
    });
  });

  describe('useDateRange hook', () => {
    it('initializes with default preset and range', () => {
      const { result } = renderHook(() => useDateRange());
      expect(result.current.selectedPreset).toBe('last30days');
      expect(result.current.dateRange).toEqual(getDateRangeFromPreset('last30days'));
    });

    it('handles preset changes', () => {
      const { result } = renderHook(() => useDateRange());
      
      act(() => {
        result.current.handlePresetChange('last7days');
      });
      expect(result.current.selectedPreset).toBe('last7days');
      expect(result.current.dateRange).toEqual(getDateRangeFromPreset('last7days'));

      // Change to custom (should not update dateRange automatically)
      act(() => {
        result.current.handlePresetChange('custom');
      });
      expect(result.current.selectedPreset).toBe('custom');
    });

    it('handles custom range setting', () => {
      const { result } = renderHook(() => useDateRange());
      const customRange = { from: new Date('2026-01-01'), to: new Date('2026-01-10') };

      act(() => {
        result.current.setCustomRange(customRange);
      });

      expect(result.current.selectedPreset).toBe('custom');
      expect(result.current.dateRange).toEqual(customRange);
    });
  });
});
