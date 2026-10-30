import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AcceptInvitation from '../AcceptInvitation';
import PatientPortal from '../PatientPortal';
import PublicBooking from '../PublicBooking';
import ResetPassword from '../ResetPassword';
import { authApi } from '@/services/api';

const APPOINTMENT_TYPE_ID = '11111111-1111-4111-8111-111111111111';
const PROVIDER_ID = '22222222-2222-4222-8222-222222222222';

function SuccessDestination() {
  const location = useLocation();
  const state = (location.state || {}) as { requestedDate?: string; requestedTime?: string };
  return (
    <div>
      Success destination
      <span data-testid="success-date">{state.requestedDate}</span>
      <span data-testid="success-time">{state.requestedTime}</span>
    </div>
  );
}

function renderRoute(ui: React.ReactElement, path = '/', routePattern = '*') {
  window.history.replaceState({}, '', path);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePattern} element={ui} />
          <Route path="/book/success" element={<SuccessDestination />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function jsonResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Server Error',
    json: async () => data,
  } as Response);
}

function bookingPage(overrides: Record<string, unknown> = {}) {
  return {
    page_slug: 'demo',
    page_title: 'Bright Smiles Booking',
    welcome_message: 'Welcome to our practice',
    logo_url: null,
    primary_color: '#2563EB',
    background_image_url: null,
    allow_new_patients: true,
    allow_existing_patients: true,
    require_phone_verification: false,
    require_email_verification: false,
    booking_window_days: 30,
    min_notice_hours: 24,
    practice_timezone: 'America/Chicago',
    business_hours: {},
    blocked_dates: [],
    allowed_appointment_types: [APPOINTMENT_TYPE_ID],
    appointment_types: [{
      id: APPOINTMENT_TYPE_ID,
      name: 'Dental Checkup',
      duration_minutes: 30,
      description: 'Regular examination',
      color: '#2563EB',
      icon: '🦷',
    }],
    providers: [{ id: PROVIDER_ID, name: 'Dr. Dana Dentist' }],
    intake_form_fields: [],
    require_insurance_info: false,
    require_medical_history: false,
    captcha_required: false,
    ...overrides,
  };
}

describe('high-impact public routes', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('covers reset-password invalid, validation, and success states', async () => {
    const resetSpy = vi.spyOn(authApi, 'resetPassword').mockResolvedValue({ success: true });
    const invalid = renderRoute(<ResetPassword />, '/reset-password');
    expect(screen.getByRole('heading', { name: 'Invalid Link' })).toBeInTheDocument();
    invalid.unmount();

    renderRoute(<ResetPassword />, '/reset-password#token=reset-token');
    fireEvent.click(screen.getByRole('button', { name: /update password/i }));
    expect(await screen.findByText('Password must contain at least one special character')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('New Password'), {
      target: { value: 'StrongPass1!' },
    });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'StrongPass1!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /update password/i }));

    expect(await screen.findByRole('heading', { name: 'Password Reset Complete' })).toBeInTheDocument();
    expect(resetSpy).toHaveBeenCalledWith({ token: 'reset-token', password: 'StrongPass1!' });
  });

  it('validates and accepts a staff invitation', async () => {
    vi.spyOn(authApi, 'validateInvitation').mockResolvedValue({
      success: true,
      data: {
        email: 'dentist@example.com',
        firstName: 'Dana',
        lastName: 'Dentist',
        role: 'dentist',
        practiceName: 'Bright Smiles',
        invitedBy: 'Owner User',
        isValid: true,
      },
    });
    const acceptSpy = vi.spyOn(authApi, 'acceptInvitation').mockResolvedValue({ success: true });

    renderRoute(<AcceptInvitation />, '/accept-invitation#token=invite-token');
    expect(await screen.findByText('Join Bright Smiles')).toBeInTheDocument();

    const passwordInputs = screen.getAllByPlaceholderText('••••••••');
    fireEvent.change(passwordInputs[0], { target: { value: 'StrongPass1!' } });
    fireEvent.change(passwordInputs[1], { target: { value: 'StrongPass1!' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByRole('heading', { name: 'Welcome to the Team!' })).toBeInTheDocument();
    expect(acceptSpy).toHaveBeenCalledWith({ token: 'invite-token', password: 'StrongPass1!' });
  });

  it('shows a configured-empty state instead of fake services', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse(bookingPage({ appointment_types: [], allowed_appointment_types: [] }))));

    renderRoute(<PublicBooking />, '/book/smile/demo', '/book/:practiceSlug/:slug');

    expect(await screen.findByText('No services are currently available online')).toBeInTheDocument();
    expect(screen.queryByText('Dental Checkup')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('shows a configuration error when neither patient mode is allowed', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse(bookingPage({
      allow_new_patients: false,
      allow_existing_patients: false,
    }))));

    renderRoute(<PublicBooking />, '/book/smile/demo', '/book/:practiceSlug/:slug');

    expect(await screen.findByRole('heading', { name: 'Online booking is not configured' })).toBeInTheDocument();
    expect(screen.getByText(/not accepting new or existing patients/i)).toBeInTheDocument();
  });

  it('uses canonical availability, submits the slot provider, and gates success on phone verification', async () => {
    let bookingPayload: Record<string, unknown> | undefined;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/availability')) {
        const request = JSON.parse(String(init?.body)) as { start_date: string };
        return jsonResponse({
          days: [{
            date: request.start_date,
            day_of_week: 'Monday',
            is_available: true,
            slots: [{
              start_time: '09:00:00',
              end_time: '09:30:00',
              duration_minutes: 30,
              is_available: true,
              provider_id: PROVIDER_ID,
              provider_name: 'Dr. Dana Dentist',
            }],
          }],
          total_slots: 1,
        });
      }
      if (url.endsWith('/book')) {
        bookingPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return jsonResponse({
          confirmation_code: 'ABC12345',
          status: 'pending',
          first_name: 'Pat',
          last_name: 'Patient',
          requested_date: bookingPayload.requested_date,
          requested_time: '09:00:00',
          verification_session: 'phone-session',
          require_email_verification: false,
          require_phone_verification: true,
          email_verified: true,
          phone_verified: false,
          message: 'Booking request submitted successfully',
        });
      }
      if (url.endsWith('/verify-phone')) {
        expect(JSON.parse(String(init?.body))).toEqual({
          verification_session: 'phone-session',
          verification_code: '123456',
        });
        return jsonResponse({
          verified: true,
          message: 'Phone verified successfully',
          confirmation_code: 'ABC12345',
          email_verified: true,
          phone_verified: true,
          require_email_verification: false,
          require_phone_verification: true,
        });
      }
      return jsonResponse(bookingPage({ require_phone_verification: true, min_notice_hours: 36 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    renderRoute(<PublicBooking />, '/book/smile/demo', '/book/:practiceSlug/:slug');
    expect(await screen.findByText('Bright Smiles Booking')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Dental Checkup/i }));
    expect(await screen.findByText("Appointments require at least 36 hours' notice.")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /09:00/i }));
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));

    fireEvent.click(await screen.findByLabelText('Existing patient'));
    fireEvent.change(screen.getByLabelText('First Name'), { target: { value: 'Pat' } });
    fireEvent.change(screen.getByLabelText('Last Name'), { target: { value: 'Patient' } });
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'pat@example.com' } });
    fireEvent.change(screen.getByLabelText('Phone Number'), { target: { value: '(555) 123-4567' } });
    expect(screen.getByRole('button', { name: /Continue/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Date of Birth'), { target: { value: '1990-01-02' } });
    expect(screen.getByRole('button', { name: /Continue/i })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));

    fireEvent.click(await screen.findByRole('button', { name: /Confirm Booking/i }));
    expect(await screen.findByRole('heading', { name: 'Verify your booking request' })).toBeInTheDocument();
    expect(bookingPayload).toMatchObject({
      appointment_type_id: APPOINTMENT_TYPE_ID,
      provider_id: PROVIDER_ID,
      phone: '5551234567',
      date_of_birth: '1990-01-02',
      is_new_patient: false,
    });

    fireEvent.change(screen.getByLabelText('Phone verification code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Verify phone' }));
    expect(await screen.findByText('Success destination')).toBeInTheDocument();
  });

  it('automatically exchanges email fragment tokens and completes verification', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/verify-email')) {
        expect(JSON.parse(String(init?.body))).toEqual({
          verification_session: 'email-session',
          verification_token: 'email-token',
        });
        return jsonResponse({
          verified: true,
          message: 'Email verified successfully',
          confirmation_code: 'EMAIL123',
          email_verified: true,
          phone_verified: true,
          require_email_verification: true,
          require_phone_verification: false,
        });
      }
      return jsonResponse(bookingPage({ require_email_verification: true }));
    });
    vi.stubGlobal('fetch', fetchMock);
    sessionStorage.setItem('coredent-booking-verification:email-session', JSON.stringify({
      requestedDate: '2026-07-01',
      requestedTime: '09:00:00',
    }));

    renderRoute(
      <PublicBooking />,
      '/book/smile/demo#verification_session=email-session&email_token=email-token',
      '/book/:practiceSlug/:slug',
    );

    expect(await screen.findByText('Success destination')).toBeInTheDocument();
    expect(screen.getByTestId('success-date')).toHaveTextContent('2026-07-01');
    expect(screen.getByTestId('success-time')).toHaveTextContent('09:00:00');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/booking/public/verify-email'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('logs into the patient portal, loads all dashboard feeds, and signs out', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/portal/access/verify')) {
        // Step 2: the emailed code is exchanged for the portal session.
        return jsonResponse({
          access_token: 'portal-token',
          patient_name: 'Pat Patient',
          practice_name: 'Bright Smiles',
          expires_at: '2026-06-24T00:00:00Z',
        });
      }
      if (url.endsWith('/portal/access')) {
        // Step 1: identity matched; the magic link is emailed (body unused).
        return jsonResponse({});
      }
      if (url.includes('/appointments')) {
        return jsonResponse({ appointments: [{
          id: 'appt-1', start_time: '2026-07-01T09:00:00Z', end_time: '2026-07-01T09:30:00Z',
          status: 'confirmed', reason: 'Cleaning', notes: null, provider_name: 'Dr. Dana',
        }] });
      }
      if (url.includes('/billing')) {
        return jsonResponse({ invoices: [{
          id: 'inv-1', invoice_number: 'INV-1', date: '2026-06-01', total_amount: 150,
          amount_paid: 50, balance_due: 100, status: 'pending', description: 'Cleaning',
        }], total_outstanding: 100 });
      }
      if (url.includes('/treatment-plans')) {
        return jsonResponse({ treatment_plans: [{
          id: 'plan-1', plan_name: 'Restorative Plan', status: 'proposed', total_estimated_cost: 900,
          total_insurance_estimate: 500, total_patient_responsibility: 400, created_date: '2026-06-01',
          diagnosis: 'Caries', treatment_goals: 'Restore tooth',
        }] });
      }
      if (url.includes('/insurance')) {
        return jsonResponse({ insurance: [{
          id: 'ins-1', insurance_type: 'PPO', subscriber_id: 'SUB-1', group_number: 'G-1',
          effective_date: '2026-01-01', annual_maximum: 2000, annual_deductible: 50,
          deductible_met: 25, preventive_coverage: 100, basic_coverage: 80, major_coverage: 50,
        }] });
      }
      if (url.includes('/documents')) {
        return jsonResponse({ documents: [{
          id: 'doc-1', name: 'Consent Form', type: 'consent', is_completed: false,
          content: null, assigned_date: '2026-06-01', completed_date: null,
        }] });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<PatientPortal />);
    fireEvent.change(screen.getByPlaceholderText('e.g. bright-smiles-dental'), { target: { value: 'bright-smiles' } });
    fireEvent.change(screen.getByPlaceholderText('your@email.com'), { target: { value: 'pat@example.com' } });
    fireEvent.change(document.querySelector('input[type="date"]')!, { target: { value: '1990-01-01' } });
    // Two-step magic-link sign-in (mirrors PatientPortal.tsx PortalLogin).
    fireEvent.click(screen.getByRole('button', { name: 'Email Me a Sign-In Link' }));
    const codeInput = await screen.findByPlaceholderText('Paste the code from your email link');
    fireEvent.change(codeInput, { target: { value: 'magic-code-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign In With Code' }));

    expect(await screen.findByRole('heading', { name: /Welcome back, Pat/i })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(6));
    expect(screen.getByRole('tab', { name: 'Billing' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Sign Out/i }));
    expect(await screen.findByRole('heading', { name: 'Patient Portal' })).toBeInTheDocument();
  });
});
