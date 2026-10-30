import { beforeEach, describe, expect, it, vi } from 'vitest';
import { bookingApi } from '@/services/bookingApi';
import { enterpriseApi } from '@/services/enterpriseApi';
import { inventoryApi } from '@/services/inventoryApi';
import { apiClient } from '@/services/api';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('live operations API contracts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({ success: true, data: {} } as never);
    vi.mocked(apiClient.post).mockResolvedValue({ success: true, data: {} } as never);
    vi.mocked(apiClient.put).mockResolvedValue({ success: true, data: {} } as never);
  });

  it('uses the staff booking routes and wire parameters', async () => {
    await bookingApi.listBookings({ status_filter: 'pending', limit: 100 });
    await bookingApi.confirmBooking('booking-1', {
      booking_id: 'booking-1',
      create_appointment: true,
      send_confirmation: true,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/booking/bookings/', {
      status_filter: 'pending',
      limit: 100,
    });
    expect(apiClient.post).toHaveBeenCalledWith('/booking/bookings/booking-1/confirm', {
      booking_id: 'booking-1',
      create_appointment: true,
      send_confirmation: true,
    });
  });

  it('uses the inventory list route with low-stock filtering', async () => {
    await inventoryApi.listItems({ low_stock: true, page: 1, limit: 100 });

    expect(apiClient.get).toHaveBeenCalledWith('/inventory/items/', {
      low_stock: true,
      page: 1,
      limit: 100,
    });
  });

  it('uses group-scoped Enterprise endpoints and date parameters', async () => {
    await enterpriseApi.getGroupAnalytics({ start_date: '2026-07-28', end_date: '2026-08-26' });
    await enterpriseApi.listGroupPractices({ page: 1, limit: 100 });

    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/enterprise/group/analytics', {
      start_date: '2026-07-28',
      end_date: '2026-08-26',
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/enterprise/group/practices', {
      page: 1,
      limit: 100,
    });
  });
});
