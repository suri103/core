// ============================================
// CoreDent PMS - Treatment Plan Dialog
// Create treatment plans with practice-scoped patient/provider UUIDs
// ============================================

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { patientsApi } from '@/services/api';
import { schedulingApi } from '@/services/schedulingApi';
import type { TreatmentPlan, TreatmentPlanCreateInput } from '@/types/treatmentPlan';

const planSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(255, 'Title too long'),
  patientId: z.string().uuid('Select a valid patient'),
  providerId: z.string().uuid('Select a valid provider'),
  treatmentGoals: z.string().trim().max(2000, 'Treatment goals too long').optional(),
  notes: z.string().trim().max(2000, 'Notes too long').optional(),
});

type PlanFormValues = z.infer<typeof planSchema>;

interface TreatmentPlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan?: TreatmentPlan | null;
  onSubmit: (data: TreatmentPlanCreateInput) => Promise<boolean | void> | boolean | void;
}

export function TreatmentPlanDialog({
  open,
  onOpenChange,
  plan,
  onSubmit,
}: TreatmentPlanDialogProps) {
  const isEditing = !!plan;
  const [patientSearch, setPatientSearch] = React.useState('');
  const { data: patientsResponse, isLoading: patientsLoading } = useQuery({
    queryKey: ['patients', 'treatment-plan-options', patientSearch],
    queryFn: () => patientsApi.list({
      status: 'active',
      limit: 100,
      search: patientSearch.trim() || undefined,
    }),
    enabled: open,
  });
  const { data: providers = [], isLoading: providersLoading } = useQuery({
    queryKey: ['providers', 'treatment-plan-options'],
    queryFn: () => schedulingApi.getProviders(),
    enabled: open,
  });

  const patients = patientsResponse?.data?.data ?? [];
  const eligibleProviders = providers.filter((provider) => {
    const role = String(provider.role).toLowerCase();
    return role === 'dentist' || role === 'owner';
  });

  const form = useForm<PlanFormValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      title: plan?.title || '',
      patientId: plan?.patientId || '',
      providerId: plan?.providerId || '',
      treatmentGoals: plan?.treatmentGoals || '',
      notes: plan?.notes || '',
    },
  });

  React.useEffect(() => {
    if (open) {
      form.reset({
        title: plan?.title || '',
        patientId: plan?.patientId || '',
        providerId: plan?.providerId || '',
        treatmentGoals: plan?.treatmentGoals || '',
        notes: plan?.notes || '',
      });
    }
  }, [open, plan, form]);

  const handleSubmit = async (values: PlanFormValues) => {
    const patient = patients.find((item) => item.id === values.patientId);
    const provider = eligibleProviders.find((item) => item.id === values.providerId);
    const result = await onSubmit({
      title: values.title,
      patientId: values.patientId,
      providerId: values.providerId,
      patientName: patient ? `${patient.firstName} ${patient.lastName}`.trim() : undefined,
      providerName: provider?.name,
      treatmentGoals: values.treatmentGoals?.trim() || undefined,
      notes: values.notes?.trim() || undefined,
    });
    if (result !== false) onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Edit Treatment Plan' : 'Create Treatment Plan'}
          </DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Plan Title</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g., Comprehensive Restoration Plan" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-2">
              <FormLabel htmlFor="treatment-patient-search">Find Patient</FormLabel>
              <Input
                id="treatment-patient-search"
                value={patientSearch}
                onChange={(event) => setPatientSearch(event.target.value)}
                placeholder="Search active patients by name, email, or phone"
              />
              <p className="text-xs text-muted-foreground">
                Search the practice directory, then select the matching patient record.
              </p>
            </div>

            <FormField
              control={form.control}
              name="patientId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Patient</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} disabled={patientsLoading}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={patientsLoading ? 'Loading patients…' : 'Select patient'} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {patients.map((patient) => (
                        <SelectItem key={patient.id} value={patient.id}>
                          {patient.firstName} {patient.lastName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="providerId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Provider</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange} disabled={providersLoading}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={providersLoading ? 'Loading providers…' : 'Select provider'} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {eligibleProviders.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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
                      placeholder="Clinical goals for this treatment plan…"
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
                      placeholder="Notes for the dental team…"
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
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {isEditing ? 'Save Changes' : 'Create Plan'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
