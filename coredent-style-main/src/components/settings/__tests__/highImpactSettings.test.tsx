import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppointmentTypesTab } from '../AppointmentTypesTab';
import { AutomationsTab } from '../AutomationsTab';
import { BillingPreferencesTab } from '../BillingPreferencesTab';
import { ChairsTab } from '../ChairsTab';
import { StaffSettingsTab } from '../StaffSettingsTab';
import { WorkingHoursTab } from '../WorkingHoursTab';
import { automationApi } from '@/services/automationApi';
import { clinicApi } from '@/services/clinicApi';
import { settingsApi } from '@/services/api';
import { staffApi } from '@/services/staffApi';
import { defaultBillingPreferences } from '@/types/settings';
import { defaultWorkingHours } from '@/types/clinic';
import type { AppointmentTypeConfig, Chair } from '@/types/clinic';
import type { AutomationWebhook } from '@/types/automation';
import type { StaffInvitation, StaffMember } from '@/types/staff';

const appointmentType: AppointmentTypeConfig = {
  id: 'type-1',
  name: 'Cleaning',
  code: 'D1110',
  duration: 45,
  color: '#3B82F6',
  isActive: true,
  allowOnlineBooking: true,
  description: 'Preventive cleaning',
};

const chair: Chair = {
  id: 'chair-1',
  name: 'Operatory 1',
  description: 'Main room',
  isActive: true,
  color: '#10B981',
};

const staffMember: StaffMember = {
  id: 'staff-1',
  firstName: 'Dana',
  lastName: 'Dentist',
  email: 'dana@example.com',
  role: 'dentist',
  status: 'active',
};

const invitation: StaffInvitation = {
  id: 'invite-1',
  email: 'new@example.com',
  firstName: 'New',
  lastName: 'Member',
  role: 'front_desk',
  invitedByName: 'Owner User',
  expiresAt: '2026-07-01T00:00:00Z',
};

const webhook: AutomationWebhook = {
  id: 'hook-1',
  name: 'Appointment SMS',
  url: 'https://hooks.example.test/appointments',
  event: 'appointment_booked',
  isActive: true,
  secretToken: 'secret',
};

describe('high-impact settings components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  it('creates an appointment type', async () => {
    const onUpdate = vi.fn();
    vi.spyOn(clinicApi, 'createAppointmentType').mockResolvedValue({
      success: true,
      data: { ...appointmentType, id: 'type-2', name: 'Emergency' },
    });

    render(<AppointmentTypesTab appointmentTypes={[appointmentType]} onUpdate={onUpdate} />);
    expect(screen.getByText('Preventive cleaning')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Add Type/i }));
    fireEvent.change(screen.getByLabelText('Type Name'), { target: { value: 'Emergency' } });
    fireEvent.change(screen.getByLabelText(/Duration/i), { target: { value: '60' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Type' }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
  });

  it('creates an operatory chair', async () => {
    const onUpdate = vi.fn();
    vi.spyOn(clinicApi, 'createChair').mockResolvedValue({
      success: true,
      data: { ...chair, id: 'chair-2', name: 'Operatory 2' },
    });

    render(<ChairsTab chairs={[chair]} onUpdate={onUpdate} />);
    fireEvent.click(screen.getByRole('button', { name: /Add Operatory/i }));
    fireEvent.change(screen.getByLabelText(/Chair\/Operatory Name/i), { target: { value: 'Operatory 2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Chair' }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
  });

  it('updates working hours and billing preferences', async () => {
    const hoursUpdate = vi.fn();
    vi.spyOn(clinicApi, 'updateSettings').mockResolvedValue({ success: true, data: undefined });
    const hours = render(<WorkingHoursTab workingHours={defaultWorkingHours} onUpdate={hoursUpdate} />);
    fireEvent.change(screen.getAllByDisplayValue('08:00')[0], { target: { value: '07:30' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Hours/i }));
    await waitFor(() => expect(hoursUpdate).toHaveBeenCalled());
    hours.unmount();

    const billingUpdate = vi.fn();
    vi.spyOn(settingsApi, 'updateBillingPreferences').mockResolvedValue({
      success: true,
      data: { ...defaultBillingPreferences, invoicePrefix: 'CD' },
    });
    render(<BillingPreferencesTab preferences={defaultBillingPreferences} onUpdate={billingUpdate} />);
    fireEvent.change(screen.getByLabelText('Invoice Prefix'), { target: { value: 'CD' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Preferences/i }));
    await waitFor(() => expect(billingUpdate).toHaveBeenCalledWith(expect.objectContaining({ invoicePrefix: 'CD' })));
  });

  it('loads staff, changes status, cancels an invitation, and sends a new invitation', async () => {
    vi.spyOn(staffApi, 'list').mockResolvedValue({
      success: true,
      data: { data: [staffMember], total: 1, page: 1, limit: 20, totalPages: 1 },
    });
    vi.spyOn(staffApi, 'listInvitations').mockResolvedValue({ success: true, data: [invitation] });
    vi.spyOn(staffApi, 'deactivate').mockResolvedValue({
      success: true,
      data: { ...staffMember, status: 'inactive' },
    });
    const cancelSpy = vi.spyOn(staffApi, 'cancelInvitation').mockResolvedValue({ success: true });
    const inviteSpy = vi.spyOn(staffApi, 'invite').mockResolvedValue({
      success: true,
      data: { ...invitation, id: 'invite-2', email: 'colleague@practice.com' },
    });

    render(<StaffSettingsTab />);
    expect(await screen.findByText('Dana Dentist')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Active/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(cancelSpy).toHaveBeenCalledWith('invite-1'));

    fireEvent.click(screen.getByRole('button', { name: /Invite Member/i }));
    fireEvent.change(screen.getByLabelText('First Name'), { target: { value: 'Casey' } });
    fireEvent.change(screen.getByLabelText('Last Name'), { target: { value: 'Colleague' } });
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'colleague@practice.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send Invitation' }));
    await waitFor(() => expect(inviteSpy).toHaveBeenCalled());
  });

  it('loads, tests, and registers automation webhooks', async () => {
    vi.spyOn(automationApi, 'getWebhooks').mockResolvedValue([webhook]);
    const testSpy = vi.spyOn(automationApi, 'testWebhook').mockResolvedValue(true);
    vi.spyOn(automationApi, 'createWebhook').mockResolvedValue({ ...webhook, id: 'hook-2', name: 'Billing Hook' });

    render(<AutomationsTab />);
    expect(await screen.findByText('Appointment SMS')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Test Link/i }));
    await waitFor(() => expect(testSpy).toHaveBeenCalledWith(webhook.url, webhook.secretToken));

    fireEvent.click(screen.getByRole('button', { name: /Add Webhook/i }));
    fireEvent.change(screen.getByLabelText('Trigger Name'), { target: { value: 'Billing Hook' } });
    fireEvent.change(screen.getByLabelText('Endpoint Webhook URL'), { target: { value: 'https://hooks.example.test/billing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Register Webhook' }));
    expect(await screen.findByText('Billing Hook')).toBeInTheDocument();
  });
});