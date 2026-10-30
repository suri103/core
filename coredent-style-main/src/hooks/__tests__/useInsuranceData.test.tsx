import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useInsuranceData } from '../useInsuranceData';

const { mockGetCarriers, mockGetClaims, mockGetPreAuthorizations } = vi.hoisted(() => ({
  mockGetCarriers: vi.fn(),
  mockGetClaims: vi.fn(),
  mockGetPreAuthorizations: vi.fn(),
}));

vi.mock('@/services/insuranceApi', () => ({
  insuranceApi: {
    getCarriers: mockGetCarriers,
    getClaims: mockGetClaims,
    getPreAuthorizations: mockGetPreAuthorizations,
  },
}));

const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: mockToast }) }));

const page = <T,>(items: T[]) => ({
  items,
  count: items.length,
  total: items.length,
  limit: 50,
  offset: 0,
  nextOffset: null,
});

describe('useInsuranceData Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCarriers.mockResolvedValue([{ id: 'carrier-1', name: 'Carrier A' }]);
    mockGetClaims.mockResolvedValue(page([{ id: 'claim-1' }]));
    mockGetPreAuthorizations.mockResolvedValue(page([{ id: 'pre-auth-1', status: 'approved' }]));
  });

  it('loads implemented insurance resources and unwraps list pages', async () => {
    const { result } = renderHook(() => useInsuranceData());
    expect(result.current.isLoading).toBe(true);

    await act(async () => undefined);

    expect(mockGetCarriers).toHaveBeenCalled();
    expect(mockGetClaims).toHaveBeenCalled();
    expect(mockGetPreAuthorizations).toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.carriers).toHaveLength(1);
    expect(result.current.claims).toHaveLength(1);
    expect(result.current.preAuths).toHaveLength(1);
    expect(result.current).not.toHaveProperty('summary');
  });

  it('shows an error instead of replacing an outage with empty activity', async () => {
    mockGetCarriers.mockRejectedValueOnce(new Error('API Error'));
    const { result } = renderHook(() => useInsuranceData());

    await act(async () => undefined);

    expect(result.current.isLoading).toBe(false);
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Error', variant: 'destructive' }));
  });

  it('supports manual refetch', async () => {
    const { result } = renderHook(() => useInsuranceData());
    await act(async () => undefined);
    expect(mockGetCarriers).toHaveBeenCalledTimes(1);

    await act(async () => result.current.refetch());
    expect(mockGetCarriers).toHaveBeenCalledTimes(2);
  });
});
