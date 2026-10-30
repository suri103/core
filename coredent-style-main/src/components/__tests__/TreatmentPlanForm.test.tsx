/**
 * TreatmentPlanForm Component Tests
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { TreatmentPlanForm } from '../treatment/TreatmentPlanForm';
import type { TreatmentPlan } from '@/types/treatmentPlan';

/** Builds a fully-typed TreatmentPlan fixture so tests stay in sync with the type. */
function makePlan(overrides: Partial<TreatmentPlan> = {}): TreatmentPlan {
  return {
    id: '1',
    title: 'Root Canal Treatment',
    treatmentGoals: 'Complex root canal',
    patientId: 'p1',
    providerId: 'provider-1',
    patientName: 'John Doe',
    status: 'draft',
    totalEstimatedCost: 0,
    totalInsuranceEstimate: 0,
    totalPatientResponsibility: 0,
    procedures: [],
    phases: [],
    notes: 'Follow up required',
    ...overrides,
  };
}

describe('TreatmentPlanForm', () => {
  it('should render form with empty fields for new plan', () => {
    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByPlaceholderText('e.g., Comprehensive Restoration Plan')).toHaveValue('');
    expect(screen.getByPlaceholderText('Patient name')).toHaveValue('');
  });

  it('should populate form with plan data for editing', () => {
    const plan = makePlan({
      title: 'Root Canal Treatment',
      treatmentGoals: 'Complex root canal',
      patientName: 'John Doe',
      notes: 'Follow up required',
    });

    render(
      <TreatmentPlanForm
        plan={plan}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('Root Canal Treatment')).toBeInTheDocument();
    expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Complex root canal')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Follow up required')).toBeInTheDocument();
  });

  it('should allow entering form data', async () => {
    const user = userEvent.setup();

    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const titleInput = screen.getByPlaceholderText('e.g., Comprehensive Restoration Plan');
    await user.type(titleInput, 'Root Canal');
    await user.type(screen.getByPlaceholderText('Patient name'), 'Jane Doe');

    expect(titleInput).toHaveValue('Root Canal');
  });

  it('should call onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />
    );

    const cancelButton = screen.getByRole('button', { name: /Cancel/i });
    await user.click(cancelButton);

    expect(onCancel).toHaveBeenCalled();
  });

  it('should show Save Changes button for existing plan', () => {
    const plan = makePlan({
      title: 'Root Canal',
      treatmentGoals: 'Treatment',
      notes: 'Notes',
    });

    render(
      <TreatmentPlanForm
        plan={plan}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();
  });

  it('should show Create Plan button for new plan', () => {
    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Create Plan/i })).toBeInTheDocument();
  });

  it('should display validation errors', async () => {
    const user = userEvent.setup();

    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const submitButton = screen.getByRole('button', { name: /Create Plan/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Title is required/i)).toBeInTheDocument();
    });
  });

  it('should update form fields when user types', async () => {
    const user = userEvent.setup();

    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const titleInput = screen.getByPlaceholderText('e.g., Comprehensive Restoration Plan');
    await user.type(titleInput, 'Root Canal');

    expect(titleInput).toHaveValue('Root Canal');
  });

  it('should update optional fields', async () => {
    const user = userEvent.setup();

    render(
      <TreatmentPlanForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const descriptionInput = screen.getByPlaceholderText('Clinical goals for this treatment plan...');
    await user.type(descriptionInput, 'Test description');

    expect(descriptionInput).toHaveValue('Test description');
  });

  it('should reset form when plan prop changes', () => {
    const plan1 = makePlan({
      id: '1',
      title: 'Plan 1',
      treatmentGoals: 'Description 1',
      patientName: 'John Doe',
      notes: 'Notes 1',
    });

    const plan2 = makePlan({
      id: '2',
      title: 'Plan 2',
      treatmentGoals: 'Description 2',
      patientId: 'p2',
      patientName: 'Jane Doe',
      notes: 'Notes 2',
    });

    const { rerender } = render(
      <TreatmentPlanForm
        plan={plan1}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('Plan 1')).toBeInTheDocument();

    rerender(
      <TreatmentPlanForm
        plan={plan2}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('Plan 2')).toBeInTheDocument();
  });
});
