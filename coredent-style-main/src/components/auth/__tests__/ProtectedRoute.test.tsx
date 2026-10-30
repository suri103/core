import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "../ProtectedRoute";
import { useAuth } from "@/contexts/auth-context";
import type { AuthContextValue } from "@/contexts/auth-context";
import type { UserRole } from "@/types/api";

vi.mock("@/contexts/auth-context", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const baseAuth: Pick<AuthContextValue, "login" | "register" | "logout" | "hasRole" | "mustChangePassword" | "clearMustChangePassword"> = {
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  hasRole: vi.fn(),
  mustChangePassword: false,
  clearMustChangePassword: vi.fn(),
};

function renderRoute(roles?: UserRole[]) {
  return render(
    <MemoryRouter initialEntries={["/private"]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route
          path="/private"
          element={
            <ProtectedRoute roles={roles}>
              <div>Private content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a session loading state", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      user: null,
      role: null,
      isAuthenticated: false,
      isLoading: true,
    });

    renderRoute();
    expect(screen.getByLabelText("Checking session")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      user: null,
      role: null,
      isAuthenticated: false,
      isLoading: false,
    });

    renderRoute();
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("renders content for an authenticated permitted user", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      user: {
        id: "user-1",
        email: "owner@example.com",
        firstName: "Practice",
        lastName: "Owner",
        role: "owner",
        practiceId: "practice-1",
        practiceName: "CoreDent",
        practiceCountry: "US",
        mustChangePassword: false,
      },
      role: "owner",
      isAuthenticated: true,
      isLoading: false,
    });

    renderRoute(["owner"]);
    expect(screen.getByText("Private content")).toBeInTheDocument();
  });

  it("blocks authenticated users without the required role", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      user: {
        id: "user-2",
        email: "desk@example.com",
        firstName: "Front",
        lastName: "Desk",
        role: "front_desk",
        practiceId: "practice-1",
        practiceName: "CoreDent",
        practiceCountry: "US",
        mustChangePassword: false,
      },
      role: "front_desk",
      isAuthenticated: true,
      isLoading: false,
    });

    renderRoute(["owner", "admin"]);
    expect(screen.getByRole("alert")).toHaveTextContent("Access denied");
    expect(screen.queryByText("Private content")).not.toBeInTheDocument();
  });

  it("redirects authenticated users with mustChangePassword to force-change-password", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      mustChangePassword: true,
      user: {
        id: "user-3",
        email: "temp@example.com",
        firstName: "Temp",
        lastName: "Staff",
        role: "dentist",
        practiceId: "practice-1",
        practiceName: "CoreDent",
        practiceCountry: "US",
        mustChangePassword: true,
      },
      role: "dentist",
      isAuthenticated: true,
      isLoading: false,
    });

    render(
      <MemoryRouter initialEntries={["/private"]}>
        <Routes>
          <Route path="/force-change-password" element={<div>Force change page</div>} />
          <Route
            path="/private"
            element={
              <ProtectedRoute>
                <div>Private content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Force change page")).toBeInTheDocument();
    expect(screen.queryByText("Private content")).not.toBeInTheDocument();
  });

  it("renders content on /force-change-password even when mustChangePassword is true", () => {
    mockedUseAuth.mockReturnValue({
      ...baseAuth,
      mustChangePassword: true,
      user: {
        id: "user-3",
        email: "temp@example.com",
        firstName: "Temp",
        lastName: "Staff",
        role: "dentist",
        practiceId: "practice-1",
        practiceName: "CoreDent",
        practiceCountry: "US",
        mustChangePassword: true,
      },
      role: "dentist",
      isAuthenticated: true,
      isLoading: false,
    });

    render(
      <MemoryRouter initialEntries={["/force-change-password"]}>
        <Routes>
          <Route
            path="/force-change-password"
            element={
              <ProtectedRoute>
                <div>Force change content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Force change content")).toBeInTheDocument();
  });
});