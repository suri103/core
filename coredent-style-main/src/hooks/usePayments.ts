// ============================================
// CoreDent PMS - usePayments Hook
// ============================================

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/services/api";

export interface PaymentStats {
  todayRevenue: number;
  todayTransactions: number;
  monthRevenue: number;
  monthGrowth: number;
  pendingPayments: number;
  pendingCount: number;
  recurringRevenue: number;
}

export interface Transaction {
  id: string;
  patient: string;
  amount: number;
  type: string;
  method: string;
  status: "Completed" | "Pending" | "Failed";
  date: string;
}

export interface RecurringPlan {
  id: string;
  patient: string;
  plan: string;
  amount: number;
  frequency: string;
  nextDate: string;
  status: "Active" | "Cancelled" | "Pending";
}

export interface Terminal {
  id: string;
  name: string;
  status: "Online" | "Offline";
  location: string;
  lastTransaction: string;
}



import type { ApiResponse } from "@/types/api";

function requirePaymentData<T>(response: ApiResponse<T>, resource: string): ApiResponse<T> {
  if (response.success && response.data !== undefined) {
    return response;
  }
  throw new Error(response.error?.message || `Unable to load ${resource}`);
}

export function usePaymentStats() {
  return useQuery({
    queryKey: ["payments", "stats"],
    queryFn: async () => {
      const res = await apiClient.get<any>("/billing/summary");
      requirePaymentData(res, "payment statistics");
      const summary = res.data;
      const stats: PaymentStats = {
        todayRevenue: Number(summary.total_collected || summary.totalCollected || 0),
        todayTransactions: Number(summary.total_payments || summary.totalPayments || 0),
        monthRevenue: Number(summary.total_revenue || summary.totalRevenue || 0),
        monthGrowth: 0,
        pendingPayments: Number(summary.outstanding_balance || summary.outstandingBalance || 0),
        pendingCount: Number(summary.pending_invoices || summary.pendingInvoices || 0),
        recurringRevenue: 0,
      };
      return { success: true, data: stats };
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useTransactions(filters?: { search?: string }) {
  return useQuery({
    queryKey: ["payments", "transactions", filters],
    queryFn: async () => {
      const res = await apiClient.get<any>("/payments/transactions", filters as Record<string, unknown>);
      requirePaymentData(res, "transactions");
      const paymentsList = Array.isArray(res.data) ? res.data : (res.data?.transactions || res.data?.payments || []);
      const transactions: Transaction[] = paymentsList.map((p: any) => ({
        id: p.id,
        patient: p.patient_name || p.patientName || (typeof p.patient === 'string' ? p.patient : p.patient ? `${p.patient.first_name || ''} ${p.patient.last_name || ''}`.trim() : 'Patient'),
        amount: Number(p.amount || 0),
        type: p.type || "Payment",
        method: p.payment_method || p.paymentMethod || p.method || "Credit Card",
        status: (p.status === "completed" || p.status === "Completed") ? "Completed" : (p.status === "failed" || p.status === "Failed") ? "Failed" : "Pending",
        date: p.date || p.created_at || p.payment_date || new Date().toISOString(),
      }));
      return { success: true, data: { transactions } };
    },
    staleTime: 2 * 60 * 1000,
  });
}

export function useRecurringPlans() {
  return useQuery({
    queryKey: ["payments", "plans"],
    queryFn: async () => {
      const res = await apiClient.get<any>("/payments/plans");
      requirePaymentData(res, "recurring plans");
      const plansList = Array.isArray(res.data) ? res.data : (res.data?.plans || res.data?.payment_plans || []);
      const plans: RecurringPlan[] = plansList.map((p: any) => ({
        id: p.id,
        patient: p.patient_name || p.patientName || (typeof p.patient === 'string' ? p.patient : p.patient ? `${p.patient.first_name || ''} ${p.patient.last_name || ''}`.trim() : 'Patient'),
        plan: p.name || p.plan || 'Payment Plan',
        amount: Number(p.monthly_amount || p.amount || 0),
        frequency: p.frequency || "Monthly",
        nextDate: p.next_payment_date || p.nextDate || p.start_date || '',
        status: (p.status === "active" || p.status === "Active") ? "Active" : (p.status === "completed" || p.status === "Completed" || p.status === "cancelled" || p.status === "Cancelled") ? "Cancelled" : "Pending",
      }));
      return { success: true, data: { plans } };
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useTerminals() {
  return useQuery({
    queryKey: ["payments", "terminals"],
    queryFn: async () => {
      const res = await apiClient.get<any>("/payments/terminals");
      requirePaymentData(res, "terminals");
      return {
        success: true,
        data: {
          terminals: (res.data?.terminals || []) as Terminal[],
        },
      };
    },
    staleTime: 5 * 60 * 1000,
  });
}