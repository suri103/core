import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import LabManagement from "../LabManagement";

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe("LabManagement Page", () => {
  it("renders the page heading and new case button", () => {
    render(<LabManagement />, { wrapper: createWrapper() });
    expect(
      screen.getByRole("heading", { level: 1, name: /lab management/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new case/i })).toBeInTheDocument();
  });

  it("displays real (non-fabricated) summary metric cards", async () => {
    render(<LabManagement />, { wrapper: createWrapper() });
    expect(screen.getByText(/active cases/i)).toBeInTheDocument();
    // With the MSW handler returning no cases, the page must NOT show the old
    // hardcoded "18" fabrication — it shows an empty state instead.
    expect(screen.queryByText("18")).not.toBeInTheDocument();
    expect(await screen.findByText(/no lab cases yet/i)).toBeInTheDocument();
  });
});
