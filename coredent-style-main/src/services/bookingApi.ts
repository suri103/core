import type { ApiResponse } from '@/types/api';
import { apiClient } from './api';

export type BookingStatus = 'pending' | 'confirmed' | 'declined' | 'cancelled' | 'completed';
export type BookingPageStatus = 'active' | 'inactive' | 'paused';
export type WaitlistStatus = 'active' | 'notified' | 'booked' | 'expired' | 'cancelled';

export interface BookingPage {
  id: string;
  page_slug: string;
  practice_public_slug: string;
  page_title: string;
  status: BookingPageStatus;
  total_bookings: number;
  total_views: number;
  conversion_rate: number;
  created_at: string;
  updated_at: string;
}

export interface BookingPageListResponse {
  pages: BookingPage[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  next_offset?: number | null;
}

export interface OnlineBooking {
  id: string;
  booking_page_id: string;
  practice_id: string;
  patient_id: string | null;
  is_new_patient: boolean;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  date_of_birth: string | null;
  appointment_type_id: string;
  provider_id: string | null;
  requested_date: string;
  requested_time: string;
  duration_minutes: number;
  reason: string | null;
  chief_complaint: string | null;
  status: BookingStatus;
  confirmation_code: string;
  email_verified: boolean;
  phone_verified: boolean;
  appointment_id: string | null;
  staff_notes: string | null;
  submitted_at: string;
  confirmed_at: string | null;
  declined_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface OnlineBookingListResponse {
  bookings: OnlineBooking[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  next_offset?: number | null;
}

export interface OnlineBookingUpdate {
  status?: BookingStatus;
  patient_id?: string;
  staff_notes?: string;
  cancellation_reason?: string;
}

export interface BookingConfirmationResponse {
  booking_id: string;
  appointment_id: string | null;
  confirmation_code: string;
  status: BookingStatus;
  message: string;
}

export interface WaitlistEntry {
  id: string;
  booking_page_id: string;
  practice_id: string;
  patient_id: string | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  preferred_dates: string[];
  preferred_times: string[];
  appointment_type_id: string | null;
  reason: string | null;
  priority: number;
  status: WaitlistStatus;
  notified_count: number;
  last_notified_at: string | null;
  expires_at: string | null;
  booking_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WaitlistEntryListResponse {
  entries: WaitlistEntry[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  next_offset?: number | null;
}

export interface WaitlistEntryUpdate {
  status?: WaitlistStatus;
  priority?: number;
  booking_id?: string;
}

interface BookingListParams {
  status_filter?: BookingStatus;
  limit?: number;
  offset?: number;
}

interface WaitlistListParams {
  status_filter?: WaitlistStatus;
  limit?: number;
  offset?: number;
}

export const bookingApi = {
  listPages: (params?: { status?: BookingPageStatus; limit?: number; offset?: number }): Promise<ApiResponse<BookingPageListResponse>> =>
    apiClient.get<BookingPageListResponse>('/booking/pages/', params),

  listBookings: (params?: BookingListParams): Promise<ApiResponse<OnlineBookingListResponse>> =>
    apiClient.get<OnlineBookingListResponse>('/booking/bookings/', params as unknown as Record<string, unknown>),

  updateBooking: (bookingId: string, payload: OnlineBookingUpdate): Promise<ApiResponse<OnlineBooking>> =>
    apiClient.put<OnlineBooking>(`/booking/bookings/${bookingId}`, payload),

  confirmBooking: (
    bookingId: string,
    payload: { booking_id: string; create_appointment: boolean; send_confirmation: boolean },
  ): Promise<ApiResponse<BookingConfirmationResponse>> =>
    apiClient.post<BookingConfirmationResponse>(`/booking/bookings/${bookingId}/confirm`, payload),

  listWaitlist: (params?: WaitlistListParams): Promise<ApiResponse<WaitlistEntryListResponse>> =>
    apiClient.get<WaitlistEntryListResponse>('/booking/waitlist/', params as unknown as Record<string, unknown>),

  updateWaitlist: (entryId: string, payload: WaitlistEntryUpdate): Promise<ApiResponse<WaitlistEntry>> =>
    apiClient.put<WaitlistEntry>(`/booking/waitlist/${entryId}`, payload),

  notifyWaitlist: (entryId: string): Promise<ApiResponse<{
    message: string;
    delivery_status: string;
    provider_accepted: boolean;
    provider_message_id?: string | null;
  }>> => apiClient.post(`/booking/waitlist/${entryId}/notify`, {}),
};
