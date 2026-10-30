import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import PatientPortal from '../PatientPortal';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

beforeAll(() => {
  if (!window.PointerEvent) {
    window.PointerEvent = class PointerEvent extends MouseEvent {} as any;
  }
});

const mockSession = {
  access_token: 'test-token-123',
  patient_name: 'John Doe',
  practice_name: 'Bright Smiles Dental',
  expires_at: '2026-06-29T12:00:00Z',
};

const mockAppointments = {
  appointments: [
    {
      id: 'apt-1',
      start_time: '2026-06-28T10:00:00Z',
      end_time: '2026-06-28T10:30:00Z',
      status: 'Confirmed',
      reason: 'Cleaning',
      notes: 'No pain',
      provider_name: 'Smith',
    },
  ],
};

const mockBilling = {
  invoices: [
    {
      id: 'inv-1',
      invoice_number: 'INV-001',
      date: '2026-06-20T00:00:00Z',
      total_amount: 150,
      amount_paid: 50,
      balance_due: 100,
      status: 'Overdue',
      description: 'Exam and x-ray',
    },
  ],
  total_outstanding: 100,
};

const mockTreatments = {
  treatment_plans: [
    {
      id: 'plan-1',
      plan_name: 'Deep Cleaning Plan',
      status: 'Pending',
      total_estimated_cost: 800,
      total_insurance_estimate: 500,
      total_patient_responsibility: 300,
      created_date: '2026-06-22T00:00:00Z',
      diagnosis: 'Periodontitis',
      treatment_goals: 'Reduce pocket depths',
    },
  ],
};

const mockInsurance = {
  insurance_policies: [
    {
      id: 'ins-1',
      insurance_type: 'dental',
      subscriber_id: 'SUB-123',
      group_number: 'GRP-999',
      effective_date: '2026-01-01',
      annual_maximum: 1500,
      annual_deductible: 50,
      deductible_met: 50,
      preventive_coverage: 100,
      basic_coverage: 80,
      major_coverage: 50,
    },
  ],
};

const mockDocuments = {
  documents: [
    {
      id: 'doc-1',
      name: 'Consent Form',
      type: 'consent',
      is_completed: false,
      content: 'Agreement content details...',
      assigned_date: '2026-06-25T00:00:00Z',
      completed_date: null,
    },
  ],
};

describe('PatientPortal Page', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  describe('Login Flow', () => {
    it('renders the login form and logs in successfully', async () => {
      server.use(
        // Step 1 issues the magic link (response body is ignored on success).
        http.post('*/api/v1/portal/access', () => {
          return HttpResponse.json({});
        }),
        // Step 2 consumes the emailed code and returns the portal session.
        http.post('*/api/v1/portal/access/verify', () => {
          return HttpResponse.json(mockSession);
        }),
        http.get('*/api/v1/portal/*', () => {
          return HttpResponse.json({});
        })
      );

      const { container } = render(<PatientPortal />);

      expect(screen.getByText('Patient Portal')).toBeInTheDocument();

      const practiceCode = screen.getByPlaceholderText('e.g. bright-smiles-dental');
      const email = screen.getByPlaceholderText('your@email.com');
      const dob = container.querySelector('input[type="date"]') as HTMLInputElement;

      await userEvent.type(practiceCode, 'bright-smiles-dental');
      await userEvent.type(email, 'john@example.com');
      fireEvent.change(dob, { target: { value: '1990-01-01' } });

      // Two-step magic-link sign-in (mirrors PatientPortal.tsx PortalLogin).
      fireEvent.click(screen.getByRole('button', { name: /Email Me a Sign-In Link/i }));

      const codeInput = await screen.findByPlaceholderText('Paste the code from your email link');
      await userEvent.type(codeInput, 'magic-code-123');
      fireEvent.click(screen.getByRole('button', { name: /Sign In With Code/i }));

      await waitFor(() => {
        expect(screen.getByText('Bright Smiles Dental')).toBeInTheDocument();
      });
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('shows error on login failure', async () => {
      server.use(
        http.post('*/api/v1/portal/access', () => {
          return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 400 });
        })
      );

      const { container } = render(<PatientPortal />);

      const practiceCode = screen.getByPlaceholderText('e.g. bright-smiles-dental');
      const email = screen.getByPlaceholderText('your@email.com');
      const dob = container.querySelector('input[type="date"]') as HTMLInputElement;

      await userEvent.type(practiceCode, 'bright-smiles');
      await userEvent.type(email, 'wrong@example.com');
      fireEvent.change(dob, { target: { value: '1990-01-01' } });

      fireEvent.click(screen.getByRole('button', { name: /Email Me a Sign-In Link/i }));

      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });
    });
  });

  describe('Dashboard Flow', () => {
    const loginAndLoadDashboard = async () => {
      server.use(
        http.post('*/api/v1/portal/access', () => HttpResponse.json({})),
        http.post('*/api/v1/portal/access/verify', () => HttpResponse.json(mockSession)),
        http.get('*/api/v1/portal/appointments', () => HttpResponse.json(mockAppointments)),
        http.get('*/api/v1/portal/billing', () => HttpResponse.json(mockBilling)),
        http.get('*/api/v1/portal/treatment-plans', () => HttpResponse.json(mockTreatments)),
        http.get('*/api/v1/portal/insurance', () => HttpResponse.json(mockInsurance)),
        http.get('*/api/v1/portal/documents', () => HttpResponse.json(mockDocuments))
      );

      const { container } = render(<PatientPortal />);

      await userEvent.type(screen.getByPlaceholderText('e.g. bright-smiles-dental'), 'bright-smiles');
      await userEvent.type(screen.getByPlaceholderText('your@email.com'), 'john@example.com');
      
      const dob = container.querySelector('input[type="date"]') as HTMLInputElement;
      fireEvent.change(dob, { target: { value: '1990-01-01' } });
      
      // Two-step magic-link sign-in (mirrors PatientPortal.tsx PortalLogin):
      // step 1 emails a link, step 2 consumes the code from that link.
      fireEvent.click(screen.getByRole('button', { name: /Email Me a Sign-In Link/i }));
      const codeInput = await screen.findByPlaceholderText('Paste the code from your email link');
      await userEvent.type(codeInput, 'magic-code-123');
      fireEvent.click(screen.getByRole('button', { name: /Sign In With Code/i }));

      await waitFor(() => {
        expect(screen.getByText('Welcome back, John')).toBeInTheDocument();
      });
    };

    it('displays appointments and supports tab switching', async () => {
      await loginAndLoadDashboard();

      // Check stats cards
      expect(screen.getByText('Appointments', { selector: 'p' }).previousElementSibling).toHaveTextContent('1');
      expect(screen.getByText('Outstanding', { selector: 'p' }).previousElementSibling).toHaveTextContent('$100');
      expect(screen.getByText('Treatment Plans', { selector: 'p' }).previousElementSibling).toHaveTextContent('1');
      expect(screen.getByText('Active Policies', { selector: 'p' }).previousElementSibling).toHaveTextContent('1');

      // Check Appointments tab content
      expect(screen.getByText(/Cleaning/)).toBeInTheDocument();
      expect(screen.getByText(/Dr. Smith/)).toBeInTheDocument();

      // Switch to Billing Tab
      const billingTab = screen.getByRole('tab', { name: /Billing/i });
      await userEvent.click(billingTab);

      expect(screen.getByText('Outstanding Balance: $100')).toBeInTheDocument();
      expect(screen.getByText('INV-001')).toBeInTheDocument();
      expect(screen.getByText('Due: $100')).toBeInTheDocument();

      // Switch to Treatment Tab
      const treatmentTab = screen.getByRole('tab', { name: /Treatment/i });
      await userEvent.click(treatmentTab);

      expect(screen.getByText('Deep Cleaning Plan')).toBeInTheDocument();
      expect(screen.getByText('Periodontitis')).toBeInTheDocument();
      expect(screen.getByText('$300')).toBeInTheDocument(); // Patient responsibility

      // Switch to Insurance Tab
      const insuranceTab = screen.getByRole('tab', { name: /Insurance/i });
      await userEvent.click(insuranceTab);

      expect(screen.getByText(/dental Insurance/i)).toBeInTheDocument();
      expect(screen.getByText('Member ID: SUB-123')).toBeInTheDocument();
      expect(screen.getByText('$1,500')).toBeInTheDocument(); // Annual max

      // Switch to Digital Forms Tab
      const formsTab = screen.getByRole('tab', { name: /Digital Forms/i });
      await userEvent.click(formsTab);

      expect(screen.getByText('Consent Form')).toBeInTheDocument();
      expect(screen.getByText('Signature Required')).toBeInTheDocument();
    });

    it('supports signing digital documents', async () => {
      const canvasContext = {
        fillStyle: '',
        font: '',
        fillRect: vi.fn(),
        fillText: vi.fn(),
      } as unknown as CanvasRenderingContext2D;
      const getContextSpy = vi
        .spyOn(HTMLCanvasElement.prototype, 'getContext')
        .mockReturnValue(canvasContext);
      const toDataUrlSpy = vi
        .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
        .mockReturnValue('data:image/png;base64,test-signature');

      await loginAndLoadDashboard();

      // Go to Forms tab
      await userEvent.click(screen.getByRole('tab', { name: /Digital Forms/i }));

      const signBtn = screen.getByRole('button', { name: /Sign Now/i });
      fireEvent.click(signBtn);

      expect(screen.getByText('Sign Digital Document')).toBeInTheDocument();
      expect(screen.getByText('Agreement content details...')).toBeInTheDocument();

      const signInput = screen.getByLabelText(/Full Legal Name/i);
      const useTypedNameButton = screen.getByRole('button', { name: /Use Typed Name/i });
      const agreeCheckbox = screen.getByLabelText(/I agree that my electronic signature/i);
      const submitSignBtn = screen.getByRole('button', { name: /Agree & Sign/i });

      expect(submitSignBtn).toBeDisabled();
      expect(useTypedNameButton).toBeDisabled();

      await userEvent.type(signInput, 'John Doe');
      fireEvent.click(useTypedNameButton);
      fireEvent.click(agreeCheckbox);

      expect(submitSignBtn).toBeEnabled();

      server.use(
        http.post('*/api/v1/portal/documents/doc-1/sign', async ({ request }) => {
          expect(request.headers.get('authorization')).toBe('Bearer test-token-123');
          expect(new URL(request.url).search).toBe('');
          await expect(request.json()).resolves.toMatchObject({
            signature_data: 'data:image/png;base64,test-signature',
            signer_name: 'John Doe',
            agreement_accepted: true,
          });
          return HttpResponse.json({ success: true });
        }),
        http.get('*/api/v1/portal/documents', () => {
          return HttpResponse.json({
            documents: [
              {
                id: 'doc-1',
                name: 'Consent Form',
                type: 'consent',
                is_completed: true,
                content: 'Agreement content details...',
                assigned_date: '2026-06-25T00:00:00Z',
                completed_date: '2026-06-28T12:00:00Z',
              },
            ],
          });
        })
      );

      fireEvent.click(submitSignBtn);

      // Wait for the sign dialog to disappear
      await waitFor(() => {
        expect(screen.queryByText('Sign Digital Document')).not.toBeInTheDocument();
      });

      // Wait for the loading state to finish and dashboard to remount
      await waitFor(() => {
        expect(screen.getByText('Welcome back, John')).toBeInTheDocument();
      });

      // Since the tab reset to Appointments on remount, switch back to Digital Forms
      await userEvent.click(screen.getByRole('tab', { name: /Digital Forms/i }));

      // Now verify the document is marked as Completed
      expect(await screen.findByText('Completed')).toBeInTheDocument();
      getContextSpy.mockRestore();
      toDataUrlSpy.mockRestore();
    });

    it('supports invoice payment warning modal', async () => {
      await loginAndLoadDashboard();

      // Go to Billing
      await userEvent.click(screen.getByRole('tab', { name: /Billing/i }));

      const payBtn = screen.getByRole('button', { name: /Pay Now/i });
      fireEvent.click(payBtn);

      expect(screen.getByText('Online payment unavailable')).toBeInTheDocument();
      
      const closeBtn = screen.getByText('Close', { selector: 'button.font-bold' });
      await userEvent.click(closeBtn);

      await waitFor(() => {
        expect(screen.queryByText('Online payment unavailable')).not.toBeInTheDocument();
      });
    });

    it('supports signing out', async () => {
      await loginAndLoadDashboard();

      const signOutBtn = screen.getByRole('button', { name: /Sign Out/i });
      fireEvent.click(signOutBtn);

      expect(screen.getByText('Patient Portal')).toBeInTheDocument();
    });
  });
});
