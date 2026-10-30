import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { apiClient } from "@/services/api";
import { useApi } from "../useApi";

describe("useApi Hook", () => {
  beforeEach(() => {
    apiClient.setToken(null);
    apiClient.setRefreshToken(null);
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    apiClient.setToken(null);
    apiClient.setRefreshToken(null);
    vi.unstubAllGlobals();
  });

  it("should initialize with loading state", () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1 }), { status: 200 })
    );

    const { result } = renderHook(() => useApi("/test"));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("should handle successful data fetch through the standard API client", async () => {
    const mockData = { id: 1, name: "Test" };
    apiClient.setToken("access-token");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), { status: 200 })
    );

    const { result } = renderHook(() => useApi("/test"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/test$/),
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({ Authorization: "Bearer access-token" }),
      }),
    );
  });

  it("should handle errors", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Network failure"));

    const { result } = renderHook(() => useApi("/invalid-endpoint"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("Network failure");
  });

  it("should surface structured API error messages", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "Not found" }), { status: 404 })
    );

    const { result } = renderHook(() => useApi("/not-found"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("Not found");
  });

  it("should refetch data when calling refetch", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ version: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ version: 2 }), { status: 200 }));

    const { result } = renderHook(() => useApi("/test"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ version: 1 });

    act(() => {
      result.current.refetch();
    });

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ version: 2 });
  });
});
