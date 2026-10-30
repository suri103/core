import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Appointments from "../Appointments";

const {
  createMutate,
  deleteMutate,
  mockUseAppointments,
  reminderMutate,
  updateMutate,
} = vi.hoisted(() => ({
  createMutate: vi.fn(),
  deleteMutate: vi.fn(),
  mockUseAppointments: vi.fn(),
  reminderMutate: vi.fn(),
  updateMutate: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("@/hooks/useAppointments", () => ({
  useAppointments: mockUseAppointments,
  useAppointmentStats: () => ({
    data: { data: { todayAppointments: 5, confirmed: 1, pending: 1, cancelled: 1 } },
    isLoading: false,
    isError: false,
  }),
  useAppointmentTypes: () => ({
    data: {
      data: {
        types: [
          { id: "type-1", name: "Checkup", duration: 30 },
          { id: "type-2", name: "Cleaning", duration: 45 },
        ],
      },
    },
    isError: false,
  }),
  useCreateAppointment: (config?: { onSuccess?: () => void; onError?: () => void }) => ({
    mutate: (data: unknown) => {
      createMutate(data);
      config?.onSuccess?.();
    },
  }),
  useUpdateAppointment: (config?: { onSuccess?: () => void; onError?: () => void }) => ({
    mutate: (payload: unknown) => {
      updateMutate(payload);
      config?.onSuccess?.();
    },
  }),
  useDeleteAppointment: (config?: { onSuccess?: () => void; onError?: () => void }) => ({
    mutate: (id: string) => {
      deleteMutate(id);
      config?.onSuccess?.();
    },
  }),
  useSendAppointmentReminder: (config?: { onSuccess?: () => void; onError?: () => void }) => ({
    mutate: (id: string) => {
      reminderMutate(id);
      config?.onSuccess?.();
    },
  }),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <BrowserRouter>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </BrowserRouter>
  );
}

const appointments = [
  {
    id: "apt-1",
    patient: "Alex Rivers",
    patientName: "Alex Rivers",
    time: "09:00 AM",
    duration: "30 min",
    type: "Checkup",
    dentist: "Dr. Lee",
    status: "Confirmed",
  },
  {
    id: "apt-2",
    patient: "Blair Stone",
    patientName: "Blair Stone",
    time: "10:00 AM",
    duration: "45 min",
    type: "Cleaning",
    dentist: "Dr. Patel",
    status: "Pending",
  },
  {
    id: "apt-3",
    patient: "Casey Fox",
    patientName: "Casey Fox",
    time: "11:00 AM",
    duration: "60 min",
    type: "Root Canal",
    dentist: "Dr. Gomez",
    status: "Cancelled",
  },
  {
    id: "apt-4",
    patient: "Dev Quinn",
    patientName: "Dev Quinn",
    time: "01:00 PM",
    duration: "20 min",
    type: "Follow-up",
    dentist: "Dr. Lee",
    status: "Completed",
  },
  {
    id: "apt-5",
    patient: "Emery Noor",
    patientName: "Emery Noor",
    time: "02:00 PM",
    duration: "25 min",
    type: "Consult",
    dentist: "Dr. Patel",
    status: "Waitlisted",
  },
];

describe("high-impact Appointments workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("confirm", vi.fn(() => true));
    (window as typeof window & { __INTEGRATION_TEST__?: boolean }).__INTEGRATION_TEST__ = true;
    mockUseAppointments.mockReturnValue({
      data: { data: { appointments } },
      isLoading: false,
      isError: false,
    });
  });

  it("covers list actions, tabs, search, date changes, and form submit/cancel paths", async () => {
    const user = userEvent.setup();
    const { container } = render(<Appointments />, { wrapper });

    expect(screen.getByRole("heading", { name: "Appointments" })).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Alex Rivers")).toBeInTheDocument();
    expect(screen.getByText("Waitlisted")).toBeInTheDocument();

    const dateInput = container.querySelector('input[type="date"]');
    expect(dateInput).toBeInstanceOf(HTMLInputElement);
    await user.clear(dateInput as HTMLInputElement);
    await user.type(dateInput as HTMLInputElement, "2026-07-04");

    await user.click(screen.getByRole("tab", { name: "Timeline" }));
    expect(screen.getByText("Timeline View")).toBeInTheDocument();
    expect(screen.getAllByTestId(/appointment-apt-/)).toHaveLength(5);

    await user.click(screen.getByRole("tab", { name: "Appointment Types" }));
    expect(screen.getByText("Checkup")).toBeInTheDocument();
    expect(screen.getByText("45 minutes")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "List View" }));

    await user.click(screen.getByRole("button", { name: /new appointment/i }));
    expect(screen.getByRole("dialog", { name: /new appointment/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Patient Name"), "New Patient");
    await user.type(screen.getByLabelText("Time"), "03:00 PM");
    await user.clear(screen.getByLabelText(/duration/i));
    await user.type(screen.getByLabelText(/duration/i), "35");
    await user.type(screen.getByLabelText("Dentist"), "Dr. Smith");
    await user.click(screen.getByRole("button", { name: /create appointment/i }));

    await waitFor(() => expect(createMutate).toHaveBeenCalled());
    expect(createMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        patient: "New Patient",
        patientName: "New Patient",
        time: "03:00 PM",

        dentist: "Dr. Smith",
      }),
    );

    const firstRow = screen.getByText("Alex Rivers").closest("tr");
    expect(firstRow).toBeTruthy();
    const firstRowButtons = within(firstRow as HTMLElement).getAllByRole("button");

    await user.click(firstRowButtons[0]);
    expect(screen.getByRole("dialog", { name: /edit appointment/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /update appointment/i }));
    expect(updateMutate).toHaveBeenCalledWith({
      id: "apt-1",
      data: expect.objectContaining({ patient: "Alex Rivers" }),
    });

    await user.click(firstRowButtons[1]);
    expect(reminderMutate).toHaveBeenCalledWith("apt-1");

    await user.click(firstRowButtons[2]);
    expect(deleteMutate).toHaveBeenCalledWith("apt-1");

    await user.click(screen.getByRole("button", { name: /new appointment/i }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Search appointments..."), "Blair");
    expect(screen.getByText("Blair Stone")).toBeInTheDocument();
    expect(screen.queryByText("Alex Rivers")).not.toBeInTheDocument();
  });
});
