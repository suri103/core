import type { ApiResponse } from "@/types/api";

function apiError(response: ApiResponse<unknown>, fallbackMessage: string): Error {
  return new Error(response.error?.message || fallbackMessage);
}

export function requireApiData<T>(
  response: ApiResponse<T>,
  fallbackMessage: string,
): T {
  if (response.success && response.data !== undefined) {
    return response.data;
  }

  throw apiError(response, fallbackMessage);
}

export function requireApiSuccess(
  response: ApiResponse<unknown>,
  fallbackMessage: string,
): void {
  if (response.success) {
    return;
  }

  throw apiError(response, fallbackMessage);
}