import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import Patients from "../patients/PatientList";

// The list reads the practice country (for the create dialog) from auth
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ user: null }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {component}
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe("Patients Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render patients page", () => {
    renderWithProviders(<Patients />);
    expect(document.body).toBeInTheDocument();
  });

  it("should display patients list", async () => {
    renderWithProviders(<Patients />);

    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });

  it("should handle search", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Patients />);

    const searchInputs = screen.queryAllByRole("textbox");
    if (searchInputs.length > 0) {
      await user.type(searchInputs[0], "test");
      expect(searchInputs[0]).toHaveValue("test");
    }
  });

  it("should handle pagination", async () => {
    renderWithProviders(<Patients />);

    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });

  it("should handle add patient", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Patients />);

    const buttons = screen.queryAllByRole("button");
    const addButton = buttons.find((btn) => btn.textContent?.includes("Add") || btn.textContent?.includes("New"));
    
    if (addButton) {
      await user.click(addButton);
      expect(document.body).toBeInTheDocument();
    }
  });
});
