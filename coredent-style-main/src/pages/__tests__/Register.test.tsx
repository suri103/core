import React from 'react';
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { AuthContext } from "@/contexts/auth-context";
import type { AuthContextValue } from "@/contexts/auth-context";
import Register from "../Register";

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock Select as a native select to keep JSDOM markup valid.
vi.mock('@/components/ui/select', () => {
  function Select({ children, value, onValueChange, disabled }: any) {
    const items = React.Children.toArray(children).flatMap((child: any) => {
      if (React.isValidElement(child) && child.type === SelectContent) {
        return React.Children.toArray((child as React.ReactElement<any>).props.children);
      }
      return [];
    });

    return (
      <select
        aria-label="country"
        value={value}
        disabled={disabled}
        onChange={(e) => onValueChange(e.target.value)}
      >
        {items}
      </select>
    );
  }

  function SelectTrigger() {
    return null;
  }

  function SelectValue() {
    return null;
  }

  function SelectContent({ children }: any) {
    return <>{children}</>;
  }

  function SelectItem({ children, value }: any) {
    return <option value={value}>{children}</option>;
  }

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
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

function renderRegister(auth?: AuthContextValue) {
  const mockAuth = auth || createMockAuth();
  return {
    mockAuth,
    ...render(
      <BrowserRouter>
        <AuthContext.Provider value={mockAuth}>
          <Register />
        </AuthContext.Provider>
      </BrowserRouter>,
    )
  };
}

describe("Register Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders branding and registration form", () => {
    renderRegister();
    expect(screen.getByRole("heading", { level: 1, name: /coredent/i })).toBeInTheDocument();
    expect(screen.getByText(/get started with coredent/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/practice name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/last name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("shows validation errors for empty submit", async () => {
    const user = userEvent.setup();
    renderRegister();
    const submitBtn = screen.getByRole("button", { name: /create practice/i });
    await user.click(submitBtn);

    expect(await screen.findByText(/practice name must be at least 2 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/first name is required/i)).toBeInTheDocument();
    expect(screen.getByText(/last name is required/i)).toBeInTheDocument();
    expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
  });

  it("shows password strength validation errors", async () => {
    const user = userEvent.setup();
    renderRegister();

    await user.type(screen.getByLabelText(/practice name/i), "My Practice");
    await user.type(screen.getByLabelText(/first name/i), "John");
    await user.type(screen.getByLabelText(/last name/i), "Doe");
    await user.type(screen.getByLabelText(/email/i), "john@example.com");

    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole("button", { name: /create practice/i });

    // Too short
    await user.type(passwordInput, "short");
    await user.click(submitBtn);
    expect(await screen.findByText(/password must be at least 12 characters/i)).toBeInTheDocument();

    // No uppercase
    await user.clear(passwordInput);
    await user.type(passwordInput, "lowercase123!");
    await user.click(submitBtn);
    expect(await screen.findByText(/must include an uppercase letter/i)).toBeInTheDocument();

    // No lowercase
    await user.clear(passwordInput);
    await user.type(passwordInput, "UPPERCASE123!");
    await user.click(submitBtn);
    expect(await screen.findByText(/must include a lowercase letter/i)).toBeInTheDocument();

    // No digit
    await user.clear(passwordInput);
    await user.type(passwordInput, "NoDigitsHere!");
    await user.click(submitBtn);
    expect(await screen.findByText(/must include a digit/i)).toBeInTheDocument();

    // No special char
    await user.clear(passwordInput);
    await user.type(passwordInput, "NoSpecialChar123");
    await user.click(submitBtn);
    expect(await screen.findByText(/must include a special character/i)).toBeInTheDocument();
  });

  it("toggles password visibility when eye icon is clicked", async () => {
    const user = userEvent.setup();
    renderRegister();

    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    expect(passwordInput.type).toBe("password");

    // Click Eye button
    const toggleBtn = screen.getByRole("button", { name: "" });
    await user.click(toggleBtn);
    expect(passwordInput.type).toBe("text");

    await user.click(toggleBtn);
    expect(passwordInput.type).toBe("password");
  });

  it("submits the registration form successfully and sends the user to email verification", async () => {
    const user = userEvent.setup();
    const { mockAuth } = renderRegister();

    await user.type(screen.getByLabelText(/practice name/i), "My Practice");
    await user.type(screen.getByLabelText(/first name/i), "John");
    await user.type(screen.getByLabelText(/last name/i), "Doe");
    await user.type(screen.getByLabelText(/email/i), "john@example.com");
    await user.type(screen.getByLabelText(/password/i), "ValidPassword123!");

    const countrySelect = screen.getByRole("combobox") as HTMLSelectElement;
    await user.selectOptions(countrySelect, "IN");

    const submitBtn = screen.getByRole("button", { name: /create practice/i });
    await user.click(submitBtn);

    expect(mockAuth.register).toHaveBeenCalledWith({
      practiceName: "My Practice",
      firstName: "John",
      lastName: "Doe",
      email: "john@example.com",
      password: "ValidPassword123!",
      country: "IN",
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/login?registration=pending");
    });
  });

  it("handles failed registration and stays on the page", async () => {
    const user = userEvent.setup();
    const mockAuth = createMockAuth();
    mockAuth.register = vi.fn().mockResolvedValue(false); // Fail registration
    renderRegister(mockAuth);

    await user.type(screen.getByLabelText(/practice name/i), "My Practice");
    await user.type(screen.getByLabelText(/first name/i), "John");
    await user.type(screen.getByLabelText(/last name/i), "Doe");
    await user.type(screen.getByLabelText(/email/i), "john@example.com");
    await user.type(screen.getByLabelText(/password/i), "ValidPassword123!");

    const submitBtn = screen.getByRole("button", { name: /create practice/i });
    await user.click(submitBtn);

    expect(mockAuth.register).toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
