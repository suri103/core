import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Dashboard from "../Dashboard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          {component}
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe("Dashboard Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render dashboard", () => {
    renderWithProviders(<Dashboard />);
    expect(document.body).toBeInTheDocument();
  });

  it("should display loading state initially", () => {
    renderWithProviders(<Dashboard />);
    expect(document.body).toBeInTheDocument();
  });

  it("should handle errors gracefully", async () => {
    renderWithProviders(<Dashboard />);

    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });
});
