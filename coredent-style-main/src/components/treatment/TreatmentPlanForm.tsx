/**
 * TreatmentPlanForm Component
 * Form for creating/editing treatment plans
 */

import React from 'react';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { DialogFooter } from '@/components/ui/dialog';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Form } from '@/components/ui/form';
import type { TreatmentPlan } from '@/types/treatmentPlan';

const planSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(100, 'Title too long'),
  treatmentGoals: z.string().trim().max(2000, 'Treatment goals too long').optional(),
  patientId: z.string().min(1, 'Patient is required'),
  patientName: z.string().min(1, 'Patient name is required'),
  notes: z.string().trim().max(1000, 'Notes too long').optional(),
});

type PlanFormValues = z.infer<typeof planSchema>;

interface TreatmentPlanFormProps {
  plan?: TreatmentPlan | null;
  onSubmit: (data: PlanFormValues) => void;
  onCancel: () => void;
}

/**
 * Form component for treatment plans
 */
export const TreatmentPlanForm = React.memo(function TreatmentPlanForm({
  plan,
  onSubmit,
  onCancel,
}: TreatmentPlanFormProps) {
  const isEditing = !!plan;

  const form = useForm<PlanFormValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      title: plan?.title || '',
      treatmentGoals: plan?.treatmentGoals || '',
      patientId: plan?.patientId || '',
      patientName: plan?.patientName || '',
      notes: plan?.notes || '',
    },
  });

  // Reset form when plan changes
  React.useEffect(() => {
    form.reset({
      title: plan?.title || '',
      treatmentGoals: plan?.treatmentGoals || '',
      patientId: plan?.patientId || '',
      patientName: plan?.patientName || '',
      notes: plan?.notes || '',
    });
  }, [plan, form]);

  const handleSubmit = (values: PlanFormValues) => {
    onSubmit(values);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Plan Title</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., Comprehensive Restoration Plan"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="patientName"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Patient</FormLabel>
              <FormControl>
                <Input placeholder="Patient name" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="treatmentGoals"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Treatment Goals (optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Clinical goals for this treatment plan..."
                  className="resize-none"
                  rows={3}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Internal Notes (optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Notes for the dental team..."
                  className="resize-none"
                  rows={2}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">
            {isEditing ? 'Save Changes' : 'Create Plan'}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
});
