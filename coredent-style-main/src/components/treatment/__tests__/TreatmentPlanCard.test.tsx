import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TreatmentPlanCard } from '../TreatmentPlanCard';
import { calculatePlanSummary } from '@/types/treatmentPlan';
import type { TreatmentPlan } from '@/types/treatmentPlan';

const plan: TreatmentPlan = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'Full Mouth Restoration',
  patientId: '22222222-2222-4222-8222-222222222222',
  providerId: '33333333-3333-4333-8333-333333333333',
  patientName: 'Maya Patel',
  providerName: 'Lee Chen',
  status: 'accepted',
  totalEstimatedCost: 420,
  totalInsuranceEstimate: 125,
  totalPatientResponsibility: 295,
  phases: [],
  proceduresLoaded: true,
  procedures: [
    {
      id: 'proc-1',
      treatmentPlanId: '11111111-1111-4111-8111-111111111111',
      procedureType: 'preventive',
      adaCode: 'D1110',
      description: 'Prophylaxis',
      status: 'completed',
      fee: 120,
      insuranceEstimate: 100,
      patientResponsibility: 20,
      isCovered: true,
      coveragePercentage: 0,
      requiresPreAuth: false,
      priority: 1,
      durationMinutes: 30,
      isAccepted: true,
      displayOrder: 0,
    },
    {
      id: 'proc-2',
      treatmentPlanId: '11111111-1111-4111-8111-111111111111',
      procedureType: 'restorative',
      adaCode: 'D2391',
      description: 'Resin filling',
      status: 'planned',
      fee: 300,
      insuranceEstimate: 25,
      patientResponsibility: 275,
      isCovered: true,
      coveragePercentage: 0,
      requiresPreAuth: false,
      priority: 1,
      durationMinutes: 30,
      isAccepted: true,
      displayOrder: 1,
    },
  ],
};

describe('TreatmentPlanCard', () => {
  it('uses backend plan totals instead of simulating insurance coverage', () => {
    expect(calculatePlanSummary(plan)).toEqual({
      totalEstimatedCost: 420,
      totalInsuranceEstimate: 125,
      totalPatientResponsibility: 295,
      totalCompleted: 120,
      totalPlanned: 300,
    });
  });

  it('renders the plan and triggers actions', async () => {
    const user = userEvent.setup();
    const onView = vi.fn();
    const onEdit = vi.fn();
    const onDelete = vi.fn();

    render(<TreatmentPlanCard plan={plan} onView={onView} onEdit={onEdit} onDelete={onDelete} />);

    expect(screen.getByText('Full Mouth Restoration')).toBeInTheDocument();
    expect(screen.getByText('Patient: Maya Patel')).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
    expect(screen.getByText('$420')).toBeInTheDocument();
    expect(screen.getByText('$125')).toBeInTheDocument();
    expect(screen.getByText('$295')).toBeInTheDocument();
    expect(screen.getByText('2 procedures')).toBeInTheDocument();
    expect(screen.getByText('1 / 2 Done')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /view/i }));
    await user.click(screen.getByRole('button', { name: /designer/i }));
    await user.click(screen.getByRole('button', { name: /cancel full mouth restoration/i }));

    expect(onView).toHaveBeenCalledWith(plan);
    expect(onEdit).toHaveBeenCalledWith(plan);
    expect(onDelete).toHaveBeenCalledWith(plan);
  });
});
