import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { AuthContext } from "@/contexts/auth-context";
import type { AuthContextValue } from "@/contexts/auth-context";
import Login from "../Login";

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function createMockAuth(): AuthContextValue {
  return {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    role: null,
    mustChangePassword: false,
    login: vi.fn().mockResolvedValue(true),
    register: vi.fn().mockResolvedValue(true),
    logout: vi.fn().mockResolvedValue(undefined),
    clearMustChangePassword: vi.fn(),
    hasRole: vi.fn().mockReturnValue(false),
  };
}

function renderLogin(auth?: AuthContextValue) {
  const mockAuth = auth || createMockAuth();
  return {
    mockAuth,
    ...render(
      <BrowserRouter>
        <AuthContext.Provider value={mockAuth}>
          <Login />
        </AuthContext.Provider>
      </BrowserRouter>,
    )
  };
}

describe("Login Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders branding and form", () => {
    renderLogin();
    expect(screen.getByRole("heading", { level: 1, name: /coredent/i })).toBeInTheDocument();
    expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows validation errors for empty submit", async () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/password is required/i)).toBeInTheDocument();
  });

  it("has navigation links for forgot-password and register", () => {
    renderLogin();
    expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(screen.getByRole("link", { name: /create one/i })).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("toggles password visibility when eye icon is clicked", async () => {
    const user = userEvent.setup();
    renderLogin();

    const passwordInput = screen.getByLabelText(/^password$/i) as HTMLInputElement;
    expect(passwordInput.type).toBe("password");

    // Click Eye button with accessible name
    const toggleBtn = screen.getByRole("button", { name: /show password/i });
    await user.click(toggleBtn);
    expect(passwordInput.type).toBe("text");

    const hideBtn = screen.getByRole("button", { name: /hide password/i });
    await user.click(hideBtn);
    expect(passwordInput.type).toBe("password");
  });

  it("submits the form successfully and navigates to dashboard", async () => {
    const user = userEvent.setup();
    const { mockAuth } = renderLogin();

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockAuth.login).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "password123",
    });

    await waitFor(() => {
      // Deep links captured by ProtectedRoute redirect back after login;
      // with no blocked location the fallback is /dashboard.
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    });
  });

  it("handles failed login and stays on the login page", async () => {
    const user = userEvent.setup();
    const mockAuth = createMockAuth();
    mockAuth.login = vi.fn().mockResolvedValue(false); // Fail login
    renderLogin(mockAuth);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockAuth.login).toHaveBeenCalled();
    // Should not navigate
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
