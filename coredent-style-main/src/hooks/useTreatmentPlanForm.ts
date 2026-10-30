import { useState, useEffect, useCallback, useRef } from 'react';
import type { TreatmentPlan } from '@/types/treatmentPlan';

export interface FormData {
  title: string;
  treatmentGoals: string;
  patientName: string;
  notes: string;
}

export interface FormErrors {
  title?: string;
  treatmentGoals?: string;
  patientName?: string;
  notes?: string;
}

function getInitialFormData(plan?: TreatmentPlan | null): FormData {
  return {
    title: plan?.title || '',
    treatmentGoals: plan?.treatmentGoals || '',
    patientName: plan?.patientName || '',
    notes: plan?.notes || '',
  };
}

export function useTreatmentPlanForm(plan?: TreatmentPlan | null) {
  const [formData, setFormData] = useState<FormData>(() => getInitialFormData(plan));
  const [errors, setErrors] = useState<FormErrors>({});
  const formDataRef = useRef<FormData>(formData);

  useEffect(() => {
    formDataRef.current = formData;
  }, [formData]);

  useEffect(() => {
    const initial = getInitialFormData(plan);
    setFormData(initial);
    formDataRef.current = initial;
    setErrors({});
  }, [plan]);

  const updateField = useCallback((field: keyof FormData, value: string) => {
    const next = { ...formDataRef.current, [field]: value };
    formDataRef.current = next;
    setFormData(next);
    setErrors((previous) => {
      const nextErrors = { ...previous };
      delete nextErrors[field];
      return nextErrors;
    });
  }, []);

  const validate = useCallback((): boolean => {
    const current = formDataRef.current;
    const nextErrors: FormErrors = {};
    if (!current.title.trim()) {
      nextErrors.title = 'Title is required';
    } else if (current.title.length > 255) {
      nextErrors.title = 'Title too long';
    }
    if (!current.patientName.trim()) nextErrors.patientName = 'Patient name is required';
    if (current.treatmentGoals.length > 2000) nextErrors.treatmentGoals = 'Treatment goals too long';
    if (current.notes.length > 2000) nextErrors.notes = 'Notes too long';
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }, []);

  const reset = useCallback(() => {
    const initial = getInitialFormData(plan);
    setFormData(initial);
    formDataRef.current = initial;
    setErrors({});
  }, [plan]);

  return { formData, errors, updateField, validate, reset };
}
