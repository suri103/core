import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import ClinicalNotes from "../ClinicalNotes";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

describe("ClinicalNotes page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
  });

  it("renders the page heading", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="*" element={<ClinicalNotes />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });
});
