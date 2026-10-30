/**
 * useTreatmentPlanForm Hook Tests
 */

import { renderHook, act } from '@testing-library/react';
import { useTreatmentPlanForm } from '../useTreatmentPlanForm';
import type { TreatmentPlan } from '@/types/treatmentPlan';

/** Builds a fully-typed TreatmentPlan fixture so tests stay in sync with the type. */
function makePlan(overrides: Partial<TreatmentPlan> = {}): TreatmentPlan {
  return {
    id: '1',
    title: 'Root Canal',
    treatmentGoals: 'Complex root canal treatment',
    patientId: 'p1',
    providerId: 'provider-1',
    patientName: 'John Doe',
    status: 'draft',
    totalEstimatedCost: 0,
    totalInsuranceEstimate: 0,
    totalPatientResponsibility: 0,
    procedures: [],
    phases: [],
    notes: 'Follow up after 2 weeks',
    ...overrides,
  };
}

describe('useTreatmentPlanForm', () => {
  it('should initialize with empty form data', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    expect(result.current.formData.title).toBe('');
    expect(result.current.formData.treatmentGoals).toBe('');
    expect(result.current.formData.patientName).toBe('');
    expect(result.current.formData.notes).toBe('');
    expect(result.current.errors).toEqual({});
  });

  it('should initialize with plan data', () => {
    const plan = makePlan();

    const { result } = renderHook(() => useTreatmentPlanForm(plan));

    expect(result.current.formData.title).toBe('Root Canal');
    expect(result.current.formData.treatmentGoals).toBe('Complex root canal treatment');
    expect(result.current.formData.patientName).toBe('John Doe');
    expect(result.current.formData.notes).toBe('Follow up after 2 weeks');
  });

  it('should update field value', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'New Title');
    });

    expect(result.current.formData.title).toBe('New Title');
  });

  it('should clear error when field is updated', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.validate();
    });

    expect(result.current.errors.title).toBeDefined();

    act(() => {
      result.current.updateField('title', 'Valid Title');
    });

    expect(result.current.errors.title).toBeUndefined();
  });

  it('should validate required fields', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      const isValid = result.current.validate();
      expect(isValid).toBe(false);
    });

    expect(result.current.errors.title).toBeDefined();
    expect(result.current.errors.patientName).toBeDefined();
  });

  it('should validate title length', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'a'.repeat(256));
      const isValid = result.current.validate();
      expect(isValid).toBe(false);
    });

    expect(result.current.errors.title).toBeDefined();
  });

  it('should validate treatmentGoals length', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'Valid Title');
      result.current.updateField('patientName', 'John Doe');
      result.current.updateField('treatmentGoals', 'a'.repeat(2001));
      const isValid = result.current.validate();
      expect(isValid).toBe(false);
    });

    expect(result.current.errors.treatmentGoals).toBeDefined();
  });

  it('should validate notes length', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'Valid Title');
      result.current.updateField('patientName', 'John Doe');
      result.current.updateField('notes', 'a'.repeat(2001));
      const isValid = result.current.validate();
      expect(isValid).toBe(false);
    });

    expect(result.current.errors.notes).toBeDefined();
  });

  it('should pass validation with valid data', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'Root Canal');
      result.current.updateField('patientName', 'John Doe');
      result.current.updateField('treatmentGoals', 'Complex treatment');
      result.current.updateField('notes', 'Follow up required');
      const isValid = result.current.validate();
      expect(isValid).toBe(true);
    });

    expect(Object.keys(result.current.errors)).toHaveLength(0);
  });

  it('should reset form data', () => {
    const { result } = renderHook(() => useTreatmentPlanForm());

    act(() => {
      result.current.updateField('title', 'Root Canal');
      result.current.updateField('patientName', 'John Doe');
      result.current.reset();
    });

    expect(result.current.formData.title).toBe('');
    expect(result.current.formData.patientName).toBe('');
    expect(result.current.errors).toEqual({});
  });

  it('should handle plan updates', () => {
    const initialPlan = makePlan({
      title: 'Initial Title',
      treatmentGoals: 'Initial treatmentGoals',
      notes: 'Initial notes',
    });

    const { result, rerender } = renderHook(
      ({ plan }) => useTreatmentPlanForm(plan),
      { initialProps: { plan: initialPlan } }
    );

    expect(result.current.formData.title).toBe('Initial Title');

    const updatedPlan: TreatmentPlan = {
      ...initialPlan,
      title: 'Updated Title',
    };

    rerender({ plan: updatedPlan });

    expect(result.current.formData.title).toBe('Updated Title');
  });
});
