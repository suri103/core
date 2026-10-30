import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PatientOverviewTab } from '../PatientOverviewTab';
import type { PatientRecord } from '@/types/patient';

const patientWithNotes = {
  firstName: 'Maya',
  lastName: 'Patel',
  dateOfBirth: '1990-02-14',
  gender: 'female',
  address: {
    street: '221B Dental Ave',
    city: 'Austin',
    state: 'TX',
    zipCode: '78701',
  },
  emergencyContact: {
    name: 'Ravi Patel',
    relationship: 'Spouse',
    phone: '555-0199',
  },
  notes: [
    {
      id: 'note-1',
      type: 'general',
      content: 'Welcome note.',
      createdAt: '2026-06-01',
      createdBy: 'user-1',
      createdByName: 'Front Desk',
      isAlert: false,
      isPinned: false,
    },
    {
      id: 'note-2',
      type: 'clinical',
      content: 'Routine follow-up completed.',
      createdAt: '2026-06-02',
      createdBy: 'user-2',
      createdByName: 'Dr. Singh',
      isAlert: true,
      isPinned: false,
    },
    {
      id: 'note-3',
      type: 'billing',
      content: 'Payment plan approved.',
      createdAt: '2026-06-03',
      createdBy: 'user-3',
      createdByName: 'Billing Team',
      isAlert: false,
      isPinned: false,
    },
    {
      id: 'note-4',
      type: 'communication',
      content: 'Left voicemail.',
      createdAt: '2026-06-04',
      createdBy: 'user-4',
      createdByName: '',
      isAlert: false,
      isPinned: false,
    },
    {
      id: 'note-5',
      type: 'alert',
      content: 'Allergy on file.',
      createdAt: '2026-06-05',
      createdBy: 'user-5',
      createdByName: 'Nurse',
      isAlert: true,
      isPinned: false,
    },
  ],
} as PatientRecord;

const patientWithoutNotes = {
  ...patientWithNotes,
  emergencyContact: undefined as any,
  notes: [],
} as PatientRecord;

describe('PatientOverviewTab', () => {
  it('renders the patient timeline and add-note action', async () => {
    const user = userEvent.setup();
    const onAddNote = vi.fn();

    render(<PatientOverviewTab patient={patientWithNotes} onAddNote={onAddNote} />);

    expect(screen.getByText('Personal Details')).toBeInTheDocument();
    expect(screen.getByText('Maya Patel')).toBeInTheDocument();
    expect(screen.getByText('Ravi Patel (Spouse)')).toBeInTheDocument();
    expect(screen.getByText('Patient Notes & Timeline')).toBeInTheDocument();
    expect(screen.getByText('general')).toBeInTheDocument();
    expect(screen.getByText('clinical')).toBeInTheDocument();
    expect(screen.getByText('billing')).toBeInTheDocument();
    expect(screen.getByText('communication')).toBeInTheDocument();
    expect(screen.getByText('alert')).toBeInTheDocument();
    expect(screen.getByText('Recorded by Front Desk')).toBeInTheDocument();
    expect(screen.getByText('Recorded by Dr. Singh')).toBeInTheDocument();
    expect(screen.getByText('Recorded by Billing Team')).toBeInTheDocument();
    expect(screen.getByText('Recorded by user-4')).toBeInTheDocument();
    expect(screen.getByText('Recorded by Nurse')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /add note/i }));
    expect(onAddNote).toHaveBeenCalledTimes(1);
  });

  it('shows the empty timeline state when there are no notes or emergency contact', () => {
    render(<PatientOverviewTab patient={patientWithoutNotes} onAddNote={vi.fn()} />);

    expect(screen.getByText(/no emergency contact provided/i)).toBeInTheDocument();
    expect(screen.getByText(/no notes recorded yet/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /record first note/i })).toBeInTheDocument();
  });
});
