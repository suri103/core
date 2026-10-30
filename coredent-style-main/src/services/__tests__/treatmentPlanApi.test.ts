import { beforeEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { treatmentPlanApi } from '../treatmentPlanApi';

const planId = '11111111-1111-4111-8111-111111111111';
const patientId = '22222222-2222-4222-8222-222222222222';
const providerId = '33333333-3333-4333-8333-333333333333';
const phaseId = '44444444-4444-4444-8444-444444444444';
const procedureId = '55555555-5555-4555-8555-555555555555';

const wirePlan = {
  id: planId,
  practice_id: '66666666-6666-4666-8666-666666666666',
  patient_id: patientId,
  provider_id: providerId,
  plan_name: 'Crown restoration',
  status: 'draft',
  treatment_goals: 'Restore tooth 14',
  total_estimated_cost: '1200.00',
  total_insurance_estimate: '500.00',
  total_patient_responsibility: '700.00',
  created_date: '2026-06-01',
  created_at: '2026-06-01T12:00:00Z',
  updated_at: '2026-06-01T12:00:00Z',
};

const wireProcedure = {
  id: procedureId,
  treatment_plan_id: planId,
  phase_id: phaseId,
  procedure_type: 'restorative',
  ada_code: 'D2740',
  description: 'Crown',
  tooth_number: '14',
  surfaces: null,
  quadrant: null,
  fee: '1200.00',
  insurance_estimate: '500.00',
  patient_responsibility: '700.00',
  is_covered: true,
  coverage_percentage: 0,
  requires_pre_auth: false,
  priority: 1,
  complexity: null,
  duration_minutes: 30,
  status: 'planned',
  is_accepted: false,
  acceptance_notes: null,
  display_order: 0,
  appointment_id: null,
  pre_auth_id: null,
  created_at: '2026-06-01T12:00:00Z',
  updated_at: '2026-06-01T12:00:00Z',
};

const wirePhase = {
  id: phaseId,
  treatment_plan_id: planId,
  phase_number: 1,
  phase_name: 'Restorative phase',
  description: null,
  status: 'planned',
  display_order: 0,
};

describe('treatmentPlanApi', () => {
  beforeEach(() => server.resetHandlers());

  it('adapts the backend plan list envelope, totals, and dates', async () => {
    server.use(
      http.get('/api/v1/treatment/plans/', () =>
        HttpResponse.json({ plans: [wirePlan], count: 1, total: 1, next_offset: null }),
      ),
    );

    const result = await treatmentPlanApi.getPlans();

    expect(result).toEqual([
      expect.objectContaining({
        id: planId,
        title: 'Crown restoration',
        patientId,
        providerId,
        status: 'draft',
        treatmentGoals: 'Restore tooth 14',
        totalEstimatedCost: 1200,
        totalInsuranceEstimate: 500,
        totalPatientResponsibility: 700,
        createdDate: '2026-06-01',
        procedures: [],
        phases: [],
      }),
    ]);
  });

  it('loads a plan with procedures and real phase UUIDs from actual routes', async () => {
    server.use(
      http.get(`/api/v1/treatment/plans/${planId}`, () => HttpResponse.json(wirePlan)),
      http.get(`/api/v1/treatment/plans/${planId}/procedures`, () =>
        HttpResponse.json({ procedures: [wireProcedure], count: 1 }),
      ),
      http.get(`/api/v1/treatment/plans/${planId}/phases`, () =>
        HttpResponse.json({ phases: [wirePhase], count: 1 }),
      ),
    );

    const result = await treatmentPlanApi.getPlan(planId, {
      patientName: 'John Doe',
      providerName: 'Dana Rivera',
    });

    expect(result.patientName).toBe('John Doe');
    expect(result.providerName).toBe('Dana Rivera');
    expect(result.phases[0]).toEqual(expect.objectContaining({ id: phaseId, phaseName: 'Restorative phase' }));
    expect(result.procedures[0]).toEqual(expect.objectContaining({
      procedureType: 'restorative',
      adaCode: 'D2740',
      description: 'Crown',
      fee: 1200,
      phaseId,
    }));
  });

  it('creates a plan with only the exact backend fields', async () => {
    let requestBody: unknown;
    server.use(
      http.post('/api/v1/treatment/plans/', async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json({ ...wirePlan, plan_name: 'Bridge plan' });
      }),
    );

    const result = await treatmentPlanApi.createPlan({
      title: 'Bridge plan',
      patientId,
      providerId,
      patientName: 'John Doe',
      providerName: 'Dana Rivera',
      treatmentGoals: 'Replace missing tooth',
      notes: 'Review options',
    });

    expect(requestBody).toEqual({
      plan_name: 'Bridge plan',
      patient_id: patientId,
      provider_id: providerId,
      status: 'draft',
      treatment_goals: 'Replace missing tooth',
      notes: 'Review options',
    });
    expect(result).toEqual(expect.objectContaining({
      title: 'Bridge plan',
      patientName: 'John Doe',
      providerName: 'Dana Rivera',
    }));
  });

  it('updates plan_name and backend status through the real plan route', async () => {
    let requestBody: unknown;
    server.use(
      http.put(`/api/v1/treatment/plans/${planId}`, async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json({ ...wirePlan, plan_name: 'Presented plan', status: 'presented' });
      }),
    );

    const result = await treatmentPlanApi.updatePlan(planId, {
      title: 'Presented plan',
      status: 'presented',
    });

    expect(requestBody).toEqual({ plan_name: 'Presented plan', status: 'presented' });
    expect(result.status).toBe('presented');
  });

  it('creates a procedure with the exact backend field names', async () => {
    let requestBody: unknown;
    server.use(
      http.post(`/api/v1/treatment/plans/${planId}/procedures`, async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json(wireProcedure);
      }),
    );

    const result = await treatmentPlanApi.addProcedure(planId, {
      procedureType: 'restorative',
      adaCode: 'D2740',
      description: 'Crown',
      fee: 1200,
      toothNumber: '14',
      phaseId,
      status: 'planned',
    });

    expect(requestBody).toEqual({
      procedure_type: 'restorative',
      ada_code: 'D2740',
      description: 'Crown',
      fee: 1200,
      phase_id: phaseId,
      tooth_number: '14',
      status: 'planned',
    });
    expect(result).toEqual(expect.objectContaining({ id: procedureId, adaCode: 'D2740', phaseId }));
  });

  it('completes and deletes procedures through the actual non-nested routes', async () => {
    let completionBody: unknown;
    server.use(
      http.put(`/api/v1/treatment/procedures/${procedureId}`, async ({ request }) => {
        completionBody = await request.json();
        return HttpResponse.json({ ...wireProcedure, status: 'completed' });
      }),
      http.delete(`/api/v1/treatment/procedures/${procedureId}`, () =>
        HttpResponse.json({ message: 'Treatment procedure deleted successfully' }),
      ),
    );

    const completed = await treatmentPlanApi.completeProcedure(procedureId);
    await expect(treatmentPlanApi.deleteProcedure(procedureId)).resolves.toBeUndefined();

    expect(completionBody).toEqual({ status: 'completed' });
    expect(completed.status).toBe('completed');
  });

  it('cancels a plan through the backend delete route', async () => {
    server.use(
      http.delete(`/api/v1/treatment/plans/${planId}`, () =>
        HttpResponse.json({ message: 'Treatment plan cancelled successfully' }),
      ),
    );

    await expect(treatmentPlanApi.deletePlan(planId)).resolves.toBeUndefined();
  });
});
