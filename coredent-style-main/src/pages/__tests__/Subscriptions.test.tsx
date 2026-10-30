import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Subscriptions from "../Subscriptions";

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

describe("Subscriptions Page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the page heading and tab structure", async () => {
    render(<Subscriptions />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 1, name: /subscriptions & billing/i }),
      ).toBeInTheDocument();
    });
    // Tabs: Available Plans / My Subscription
    expect(screen.getByText(/available plans/i)).toBeInTheDocument();
    expect(screen.getByText(/my subscription/i)).toBeInTheDocument();
  });

  it("shows empty state when no plans are available", async () => {
    render(<Subscriptions />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/no plans available/i)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/contact your administrator/i),
    ).toBeInTheDocument();
  });
});
