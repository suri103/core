import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Documents from "../Documents";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <Documents />
      </QueryClientProvider>
    </BrowserRouter>,
  );
}

describe("Documents Page", () => {
  it("renders the page heading and action buttons", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 1, name: /document management/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new template/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create document/i })).toBeInTheDocument();
  });

  it("shows tab navigation for documents, templates, and e-signatures", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: /documents/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^templates$/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /e-signatures/i })).toBeInTheDocument();
  });

  it("lists documents fetched from the API in the table", async () => {
    renderPage();
    // Default tab is "documents" which shows patient documents fetched
    // via MSW from /api/v1/documents/. The page now derives its data
    // from the API instead of hardcoded mock arrays (audit finding L-5).
    expect(
      await screen.findByText(/consent form - john smith/i),
    ).toBeInTheDocument();
    expect(await screen.findByText(/treatment plan - jane doe/i)).toBeInTheDocument();
  });

  it("handles searching and tab switching", async () => {
    const user = userEvent.setup();
    renderPage();

    // Type in search
    const searchInput = screen.getByPlaceholderText(/search documents.../i);
    await user.type(searchInput, "consent");
    expect(searchInput).toHaveValue("consent");

    // Click Templates tab
    const templatesTab = screen.getByRole("tab", { name: /^templates$/i });
    await user.click(templatesTab);
    expect(await screen.findByText("Patient Consent Form")).toBeInTheDocument();

    // Click E-Signatures tab
    const signaturesTab = screen.getByRole("tab", { name: /e-signatures/i });
    await user.click(signaturesTab);
    expect(await screen.findByText("Enable E-Signatures")).toBeInTheDocument();
  });
});
