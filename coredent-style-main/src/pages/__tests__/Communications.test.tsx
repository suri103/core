import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Communications from "../Communications";

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("Communications Page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the communications page", async () => {
    render(<Communications />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/communication/i)).toBeInTheDocument();
    });
  });

  it("shows tabs for messages, templates, and reminders", async () => {
    render(<Communications />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByRole("tablist")).toBeInTheDocument();
    });
  });
});
