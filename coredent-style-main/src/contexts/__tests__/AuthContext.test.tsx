import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "../AuthContext";
import { useAuth } from "@/contexts/auth-context";

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("@/lib/analytics", () => ({
  analytics: { identify: vi.fn() },
  trackLogin: vi.fn(),
  trackLogout: vi.fn(),
  trackSignup: vi.fn(),
}));

vi.mock("@/lib/csrf", () => ({
  refreshCsrfToken: vi.fn(),
  clearCsrfToken: vi.fn(),
  getCsrfHeader: vi.fn(() => ({})),
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    // Logout clears the in-memory buffer; the mock must mirror the real
    // interface or the logout path throws an unhandled rejection.
    clearLogs: vi.fn(),
  },
}));

const authApiMock = vi.hoisted(() => ({
  restoreSession: vi.fn().mockResolvedValue(undefined),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  setToken: vi.fn(),
  setRefreshToken: vi.fn(),
}));

vi.mock("@/services/api", () => ({
  authApi: authApiMock,
}));

const TestComponent = () => {
  const { user, isAuthenticated, login, logout } = useAuth();

  return (
    <div>
      <div data-testid="auth-status">
        {isAuthenticated ? "Authenticated" : "Not Authenticated"}
      </div>
      {user && <div data-testid="user-name">{user.email}</div>}
      <button onClick={() => login({ email: "test@example.com", password: "password" })}>
        Login
      </button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();

    authApiMock.restoreSession.mockResolvedValue(undefined);
    authApiMock.getCurrentUser.mockResolvedValue({ success: false, data: null, error: { message: "Unauthorized" } });
    authApiMock.login.mockResolvedValue({ success: false, error: { message: "Invalid credentials" } });
    authApiMock.register.mockResolvedValue({ success: false, error: { message: "Registration failed" } });
    authApiMock.logout.mockResolvedValue({ success: true, data: null });
  });

  it("should provide auth context", async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );
    });

    expect(screen.getByTestId("auth-status")).toBeInTheDocument();
  });

  it("should show not authenticated initially", async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );
    });

    expect(screen.getByTestId("auth-status")).toHaveTextContent("Not Authenticated");
  });

  it("should handle login", async () => {
    const user = userEvent.setup();

    // The on-mount checkSession will use the default mock setup in beforeEach
    // We update the mock just before we click login

    await act(async () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );
    });

    // Wait for the initial mount check to finish so we know our component is ready
    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("Not Authenticated");
    });

    // Now setup the mocks for the login action
    authApiMock.login.mockResolvedValueOnce({
      success: true,
      data: { csrf_token: "csrf", access_token: "access", refresh_token: "refresh" },
    });
    authApiMock.getCurrentUser.mockResolvedValueOnce({
      success: true,
      data: {
        id: "user-1",
        email: "test@example.com",
        firstName: "Test",
        lastName: "User",
        role: "admin",
        practiceId: "practice-1",
        practiceName: "Test Practice",
      },
    });

    await user.click(screen.getByText("Login"));

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("Authenticated");
    });
  });

  it("should handle logout", async () => {
    const user = userEvent.setup();
    authApiMock.getCurrentUser.mockResolvedValueOnce({
      success: true,
      data: {
        id: "user-1",
        email: "test@example.com",
        firstName: "Test",
        lastName: "User",
        role: "admin",
        practiceId: "practice-1",
        practiceName: "Test Practice",
      },
    });

    await act(async () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("Authenticated");
    });

    await user.click(screen.getByText("Logout"));

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("Not Authenticated");
    });
  });
});
