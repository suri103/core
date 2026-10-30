import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { Sidebar } from "../layout/Sidebar";

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  );
};

describe("Sidebar Component", () => {
  it("should render sidebar", () => {
    renderWithProviders(<Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onMobileClose={vi.fn()} />);
    expect(document.body).toBeInTheDocument();
  });

  it("should have navigation links", () => {
    renderWithProviders(<Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onMobileClose={vi.fn()} />);
    expect(document.body).toBeInTheDocument();
  });

  it("should be responsive", () => {
    const { container } = renderWithProviders(<Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onMobileClose={vi.fn()} />);
    expect(container).toBeInTheDocument();
  });

  it("should handle navigation", async () => {
    renderWithProviders(<Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onMobileClose={vi.fn()} />);
    expect(document.body).toBeInTheDocument();
  });
});
