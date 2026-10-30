import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createRazorpayOrder, verifyRazorpayPayment, loadRazorpayScript } from '../paymentApi';
import { apiClient } from '../api';

vi.mock('../api', () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

describe('paymentApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clean up any added script tags from document body
    document.querySelectorAll('script[src*="checkout.razorpay.com"]').forEach((el) => el.remove());
    // Clear global window.Razorpay
    delete (window as any).Razorpay;
  });

  it('creates a Razorpay order via API', async () => {
    const mockOrderData = {
      invoice_id: 'inv-1',
      amount: 5000,
      currency: 'INR',
      receipt: 'rcpt-1',
    };

    const mockResponse = { success: true, data: { key_id: 'key', amount: 5000, currency: 'INR', order_id: 'order-1', receipt: 'rcpt-1' } };
    vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse);

    const result = await createRazorpayOrder(mockOrderData);
    expect(apiClient.post).toHaveBeenCalledWith('/payments/razorpay/order', mockOrderData);
    expect(result).toEqual(mockResponse);
  });

  it('verifies a Razorpay payment via API', async () => {
    const mockVerifyData = {
      razorpay_order_id: 'order-1',
      razorpay_payment_id: 'pay-1',
      razorpay_signature: 'sig-1',
      invoice_id: 'inv-1',
    };

    const mockResponse = { success: true, data: { payment_id: 'pay-1', verified: true } };
    vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse);

    const result = await verifyRazorpayPayment(mockVerifyData);
    expect(apiClient.post).toHaveBeenCalledWith('/payments/razorpay/verify', mockVerifyData);
    expect(result).toEqual(mockResponse);
  });

  describe('loadRazorpayScript', () => {
    it('returns true immediately if window.Razorpay is already defined', async () => {
      (window as any).Razorpay = {};
      const result = await loadRazorpayScript();
      expect(result).toBe(true);
    });

    it('creates a script element and resolves true when loaded', async () => {
      const promise = loadRazorpayScript();

      // Find the created script element
      const script = document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]') as HTMLScriptElement;
      expect(script).toBeInstanceOf(HTMLScriptElement);
      expect(script.async).toBe(true);

      // Simulate onload
      if (script.onload) {
        (script.onload as any)();
      }

      const result = await promise;
      expect(result).toBe(true);
    });

    it('resolves false when script fails to load', async () => {
      const promise = loadRazorpayScript();

      const script = document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]') as HTMLScriptElement;

      // Simulate onerror
      if (script.onerror) {
        (script.onerror as any)();
      }

      const result = await promise;
      expect(result).toBe(false);
    });
  });
});
