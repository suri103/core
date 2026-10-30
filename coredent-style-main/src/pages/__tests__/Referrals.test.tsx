import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import Referrals from "../Referrals";

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

describe("Referrals Page", () => {
  it("renders the page heading and new referral button", () => {
    render(<Referrals />, { wrapper: createWrapper() });
    expect(
      screen.getByRole("heading", { level: 1, name: /referral management/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /new referral/i }),
    ).toBeInTheDocument();
  });

  it("displays summary metric cards", () => {
    render(<Referrals />, { wrapper: createWrapper() });
    expect(screen.getByText(/total referrals/i)).toBeInTheDocument();
    // Exact match: the card subtitle "total referral fees" also contains
    // this phrase, so a substring match would find two elements.
    expect(screen.getByText(/^referral fees$/i)).toBeInTheDocument();
  });
});
