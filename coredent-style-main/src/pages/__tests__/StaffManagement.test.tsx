import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import StaffManagement from "../admin/StaffManagement";

// Mock Dialogs to easily trigger callbacks
vi.mock('@/components/admin/InviteStaffDialog', () => ({
  InviteStaffDialog: ({ open, onOpenChange, onSuccess }: any) => (
    open ? (
      <div data-testid="invite-dialog">
        <button onClick={() => onSuccess({ id: 'new-inv', email: 'new@example.com', role: 'front_desk', invitedByName: 'Admin', expiresAt: new Date(Date.now() + 86400000).toISOString() })}>
          Submit Invite
        </button>
        <button onClick={() => onOpenChange(false)}>Close Invite</button>
      </div>
    ) : null
  ),
}));

vi.mock('@/components/admin/EditStaffDialog', () => ({
  EditStaffDialog: ({ staff, open, onOpenChange, onSuccess }: any) => (
    open ? (
      <div data-testid="edit-dialog">
        <button onClick={() => onSuccess({ ...staff, role: 'owner' })}>
          Submit Edit
        </button>
        <button onClick={() => onOpenChange(false)}>Close Edit</button>
      </div>
    ) : null
  ),
}));

// Mock DropdownMenu to render items inline to avoid Radix portal/focus issues in JSDOM
vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: any) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: any) => (
    <button onClick={onClick}>{children}</button>
  ),
  DropdownMenuLabel: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSeparator: () => <div />,
}));

const mockStaff = [
  { id: '1', firstName: 'John', lastName: 'Doe', email: 'john@example.com', role: 'admin', status: 'active', lastLoginAt: '2024-03-15T10:00:00Z', avatarUrl: '' },
  { id: '2', firstName: 'Jane', lastName: 'Smith', email: 'jane@example.com', role: 'dentist', status: 'inactive', lastLoginAt: null, avatarUrl: '' },
];

const mockInvitations = [
  { id: '101', email: 'invite1@example.com', role: 'front_desk', invitedByName: 'John Doe', expiresAt: '2024-03-18T10:00:00Z' },
];

const {
  mockList,
  mockListInvitations,
  mockDeactivate,
  mockReactivate,
  mockResendInvitation,
  mockCancelInvitation
} = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockListInvitations: vi.fn(),
  mockDeactivate: vi.fn(),
  mockReactivate: vi.fn(),
  mockResendInvitation: vi.fn(),
  mockCancelInvitation: vi.fn(),
}));

vi.mock('@/services/staffApi', () => ({
  staffApi: {
    list: mockList,
    listInvitations: mockListInvitations,
    deactivate: mockDeactivate,
    reactivate: mockReactivate,
    resendInvitation: mockResendInvitation,
    cancelInvitation: mockCancelInvitation,
  },
}));

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthProvider>{children}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("StaffManagement Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      success: true,
      data: { data: mockStaff },
    });
    mockListInvitations.mockResolvedValue({
      success: true,
      data: mockInvitations,
    });
  });

  it("renders page heading and loads staff and invitations", async () => {
    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });

    // Switch to Pending Invitations tab
    const user = userEvent.setup();
    const tab = screen.getByRole("tab", { name: /Pending Invitations/i });
    await user.click(tab);

    expect(screen.getByText("invite1@example.com")).toBeInTheDocument();
  });

  it("handles loading error gracefully", async () => {
    mockList.mockRejectedValue(new Error("Failed to fetch"));
    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No staff members found")).toBeInTheDocument();
    });
  });

  it("filters staff members by search query", async () => {
    const user = userEvent.setup();
    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search by name or email/i);
    await user.type(searchInput, "Jane");

    expect(screen.queryByText("John Doe")).not.toBeInTheDocument();
    expect(screen.getByText("Jane Smith")).toBeInTheDocument();
  });

  it("handles invite staff dialog flow", async () => {
    const user = userEvent.setup();
    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    const inviteBtn = screen.getByRole("button", { name: /invite staff/i });
    await user.click(inviteBtn);

    // Verify dialog is open
    expect(screen.getByTestId("invite-dialog")).toBeInTheDocument();

    // Trigger success callback
    const submitBtn = screen.getByRole("button", { name: /submit invite/i });
    await user.click(submitBtn);

    // Verify dialog is closed (or we can just verify list updated/toast)
    const tab = screen.getByRole("tab", { name: /Pending Invitations/i });
    await user.click(tab);
    await waitFor(() => {
      expect(screen.getByText("new@example.com")).toBeInTheDocument();
    });
  });

  it("handles edit staff dialog flow", async () => {
    const user = userEvent.setup();
    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    // Since DropdownMenu is mocked inline, the "Edit Role" button is directly in the DOM
    const editOption = screen.getAllByRole("button", { name: /edit role/i })[0];
    await user.click(editOption);

    // Verify edit dialog is open
    expect(screen.getByTestId("edit-dialog")).toBeInTheDocument();

    // Trigger success callback
    const submitBtn = screen.getByRole("button", { name: /submit edit/i });
    await user.click(submitBtn);
  });

  it("handles deactivating and reactivating staff members", async () => {
    const user = userEvent.setup();
    mockDeactivate.mockResolvedValue({
      success: true,
      data: { ...mockStaff[0], status: 'inactive' },
    });
    mockReactivate.mockResolvedValue({
      success: true,
      data: { ...mockStaff[1], status: 'active' },
    });

    render(<StaffManagement />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    // 1. Deactivate John Doe
    const deactivateOption = screen.getByRole("button", { name: /deactivate/i });
    await user.click(deactivateOption);
    expect(mockDeactivate).toHaveBeenCalledWith('1');

    // 2. Reactivate Jane Smith (second row)
    await waitFor(() => {
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });
    const janeRow = screen.getByText("Jane Smith").closest("tr");
    const reactivateOption = within(janeRow!).getByRole("button", { name: /reactivate/i });
    await user.click(reactivateOption);
    expect(mockReactivate).toHaveBeenCalledWith('2');
  });

  it("handles resending and cancelling invitations", async () => {
    const user = userEvent.setup();
    mockResendInvitation.mockResolvedValue({
      success: true,
      data: mockInvitations[0],
    });
    mockCancelInvitation.mockResolvedValue({
      success: true,
    });

    render(<StaffManagement />, { wrapper: createWrapper() });

    const tab = screen.getByRole("tab", { name: /Pending Invitations/i });
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getByText("invite1@example.com")).toBeInTheDocument();
    });

    // Resend invitation (using title="Resend")
    const resendBtn = screen.getByTitle("Resend");
    await user.click(resendBtn);
    expect(mockResendInvitation).toHaveBeenCalledWith('101');

    // Cancel invitation (using title="Cancel")
    const cancelBtn = screen.getByTitle("Cancel");
    await user.click(cancelBtn);
    expect(mockCancelInvitation).toHaveBeenCalledWith('101');
  });
});
