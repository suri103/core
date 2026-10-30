import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import ForgotPassword from "../ForgotPassword";

// Mock authApi
const { mockRequestPasswordReset } = vi.hoisted(() => ({
  mockRequestPasswordReset: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  authApi: {
    requestPasswordReset: mockRequestPasswordReset,
  },
}));

// Mock Toast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

function renderForgotPassword() {
  return render(
    <BrowserRouter>
      <ForgotPassword />
    </BrowserRouter>
  );
}

describe("ForgotPassword Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the forgot password form and links", () => {
    renderForgotPassword();
    expect(screen.getByRole("heading", { name: /reset password/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send reset link/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to login/i })).toHaveAttribute("href", "/login");
  });

  it("shows validation error for invalid email", async () => {
    const user = userEvent.setup();
    renderForgotPassword();

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "invalid-email");
    fireEvent.submit(emailInput.closest('form')!);

    expect(await screen.findByText(/Please enter a valid email address/i)).toBeInTheDocument();
  });

  it("submits the form successfully and displays check email state", async () => {
    const user = userEvent.setup();
    mockRequestPasswordReset.mockResolvedValueOnce({ success: true });

    renderForgotPassword();

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "test@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(mockRequestPasswordReset).toHaveBeenCalledWith({ email: "test@example.com" });

    // Should show success view
    expect(await screen.findByText("Check Your Email")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();

    // Support "Try different email"
    await user.click(screen.getByRole("button", { name: /try different email/i }));
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("handles failed password reset requests gracefully", async () => {
    const user = userEvent.setup();
    mockRequestPasswordReset.mockResolvedValueOnce({
      success: false,
      error: { message: "Account not found" },
    });

    renderForgotPassword();

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "notfound@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(mockRequestPasswordReset).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Error',
        variant: 'destructive',
      }));
    });
  });
});
