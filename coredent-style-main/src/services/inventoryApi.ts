import type { ApiResponse } from '@/types/api';
import { apiClient } from './api';

export type InventoryCategory = 'supplies' | 'equipment' | 'medications' | 'restorative' | 'surgical' | 'disposable' | 'other';
export type InventoryUnit = 'each' | 'box' | 'pack' | 'case' | 'gallon' | 'liter';
export type InventoryTransactionType = 'IN' | 'OUT' | 'ADJUST' | 'RETURN' | 'EXPIRE';
export type InventoryAlertType = 'low_stock' | 'reorder_point' | 'expiring_soon' | 'expired' | 'out_of_stock';

export interface InventoryItem {
  id: string;
  name: string;
  description: string | null;
  sku: string | null;
  barcode: string | null;
  category: InventoryCategory | null;
  unit: InventoryUnit | null;
  units_per_package: number;
  current_quantity: number;
  minimum_quantity: number;
  reorder_quantity: number;
  maximum_quantity: number;
  unit_cost: string | null;
  unit_price: string | null;
  storage_location: string | null;
  track_expiration: boolean;
  expiration_warning_days: number;
  supplier_name: string | null;
  supplier_item_code: string | null;
  is_active: boolean;
  is_trackable: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface InventoryItemWrite {
  name: string;
  description?: string;
  sku?: string;
  category?: InventoryCategory;
  unit?: InventoryUnit;
  units_per_package?: number;
  current_quantity?: number;
  minimum_quantity?: number;
  reorder_quantity?: number;
  maximum_quantity?: number;
  unit_cost?: number;
  unit_price?: number;
  storage_location?: string;
  track_expiration?: boolean;
  expiration_warning_days?: number;
  supplier_name?: string;
  supplier_item_code?: string;
  is_active?: boolean;
  is_trackable?: boolean;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface InventoryTransaction {
  id: string;
  item_id: string;
  practice_id: string;
  user_id: string | null;
  transaction_type: InventoryTransactionType;
  quantity: number;
  previous_quantity: number;
  new_quantity: number;
  reference_type: string | null;
  reference_id: string | null;
  unit_cost: string | null;
  total_cost: string | null;
  notes: string | null;
  created_at: string | null;
}

export interface InventoryTransactionListResponse {
  transactions: InventoryTransaction[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface InventoryTransactionWrite {
  item_id: string;
  transaction_type: InventoryTransactionType;
  quantity: number;
  notes?: string;
  unit_cost?: number;
  total_cost?: number;
}

export interface InventoryAlert {
  id: string;
  item_id: string;
  practice_id: string;
  alert_type: InventoryAlertType;
  message: string | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string | null;
}

export interface InventoryAlertListResponse {
  alerts: InventoryAlert[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export const inventoryApi = {
  listItems: (params?: {
    search?: string;
    low_stock?: boolean;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<InventoryListResponse>> =>
    apiClient.get<InventoryListResponse>('/inventory/items/', params),

  createItem: (payload: InventoryItemWrite): Promise<ApiResponse<InventoryItem>> =>
    apiClient.post<InventoryItem>('/inventory/items/', payload),

  updateItem: (itemId: string, payload: Partial<InventoryItemWrite>): Promise<ApiResponse<InventoryItem>> =>
    apiClient.put<InventoryItem>(`/inventory/items/${itemId}`, payload),

  deleteItem: (itemId: string): Promise<ApiResponse<{ message: string }>> =>
    apiClient.delete<{ message: string }>(`/inventory/items/${itemId}`),

  createTransaction: (payload: InventoryTransactionWrite): Promise<ApiResponse<InventoryTransaction>> =>
    apiClient.post<InventoryTransaction>('/inventory/transactions/', payload),

  listAlerts: (params?: {
    item_id?: string;
    is_resolved?: boolean;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<InventoryAlertListResponse>> =>
    apiClient.get<InventoryAlertListResponse>('/inventory/alerts/', params),

  resolveAlert: (alertId: string): Promise<ApiResponse<InventoryAlert>> =>
    apiClient.post<InventoryAlert>(`/inventory/alerts/${alertId}/resolve`, {}),
};
