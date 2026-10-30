// ============================================
// CoreDent PMS - Payment Gateway Service (Razorpay & Stripe)
// ============================================

import { apiClient } from './api';
import type { ApiResponse } from '@/types/api';

export interface RazorpayOrderCreate {
  invoice_id: string;
  amount: number;
  currency: string;
  receipt: string;
}

export interface RazorpayPaymentVerify {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  invoice_id: string;
}

export interface RazorpayOrderDetails {
  key_id: string;
  amount: number;
  currency: string;
  order_id: string;
  receipt: string;
}

export interface RazorpayVerificationDetails {
  payment_id: string;
  verified: boolean;
}

/**
 * Creates a Razorpay order from the backend
 */
export async function createRazorpayOrder(data: RazorpayOrderCreate): Promise<ApiResponse<RazorpayOrderDetails>> {
  return apiClient.post<RazorpayOrderDetails>('/payments/razorpay/order', data);
}

/**
 * Verifies Razorpay payment signature
 */
export async function verifyRazorpayPayment(data: RazorpayPaymentVerify): Promise<ApiResponse<RazorpayVerificationDetails>> {
  return apiClient.post<RazorpayVerificationDetails>('/payments/razorpay/verify', data);
}

/**
 * Dynamically loads Razorpay checkout SDK script
 */
export async function loadRazorpayScript(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  if ((window as any).Razorpay) return true;

  return new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}
