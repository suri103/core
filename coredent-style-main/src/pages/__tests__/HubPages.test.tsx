import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RevenueLanding from "../RevenueLanding";
import ReferralHub from "../ReferralHub";
import ImagingHub from "../ImagingHub";

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

describe("RevenueLanding Page", () => {
  it("renders the page heading", () => {
    render(
      <BrowserRouter>
        <RevenueLanding />
      </BrowserRouter>
    );
    expect(screen.getByRole('heading', { name: /revenue workspace/i })).toBeInTheDocument();
  });
});

describe("ReferralHub Page", () => {
  it("renders the page heading", () => {
    const queryClient = createTestQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <ReferralHub />
        </QueryClientProvider>
      </BrowserRouter>
    );
    expect(screen.getByRole("heading", { name: /referral management/i })).toBeInTheDocument();
  });
});

describe("ImagingHub Page", () => {
  it("renders the page heading", () => {
    const queryClient = createTestQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <ImagingHub />
        </QueryClientProvider>
      </BrowserRouter>
    );
    expect(screen.getByRole("heading", { name: /imaging library/i })).toBeInTheDocument();
  });
});
