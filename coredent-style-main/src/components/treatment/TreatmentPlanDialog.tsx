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
import { Search } from 'lucide-react';
import { patientApi } from '@/services/patientApi';
import { schedulingApi } from '@/services/schedulingApi';
import type { TreatmentPlan, TreatmentPlanCreateInput } from '@/types/treatmentPlan';
import type { PatientListItem } from '@/types/patient';

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
  const [debouncedSearch, setDebouncedSearch] = React.useState('');

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(patientSearch);
    }, 250);
    return () => clearTimeout(timer);
  }, [patientSearch]);

  const { data: patients = [], isLoading: patientsLoading } = useQuery<PatientListItem[]>({
    queryKey: ['patients', 'treatment-plan-options', debouncedSearch],
    queryFn: async () => {
      const response = await patientApi.getPatients({
        query: debouncedSearch.trim() || undefined,
        limit: 100,
      });
      return Array.isArray(response?.data) ? response.data : [];
    },
    enabled: open,
  });

  const { data: providers = [], isLoading: providersLoading } = useQuery({
    queryKey: ['providers', 'treatment-plan-options'],
    queryFn: () => schedulingApi.getProviders(),
    enabled: open,
  });

  const eligibleProviders = React.useMemo(() => {
    const filtered = providers.filter((provider) => {
      const role = String(provider.role || '').toLowerCase();
      return role === 'dentist' || role === 'owner' || role === 'admin';
    });
    return filtered.length > 0 ? filtered : providers;
  }, [providers]);

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

  // Keep selected patient in the list even if a search filter would otherwise exclude them
  const selectedPatientId = form.watch('patientId');
  const displayPatients = React.useMemo(() => {
    const currentId = selectedPatientId || plan?.patientId;
    if (currentId && !patients.some((p) => p.id === currentId)) {
      const fallbackName = plan?.patientName || 'Selected Patient';
      const parts = fallbackName.split(' ');
      const existingStub: PatientListItem = {
        id: currentId,
        firstName: parts[0] || 'Selected',
        lastName: parts.slice(1).join(' ') || 'Patient',
        phone: '',
        email: '',
        dateOfBirth: '',
        status: 'active',
        hasMedicalAlerts: false,
        medicalAlerts: [],
      };
      return [existingStub, ...patients];
    }
    return patients;
  }, [patients, selectedPatientId, plan]);

  React.useEffect(() => {
    if (open) {
      setPatientSearch('');
      setDebouncedSearch('');
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
    const patient = displayPatients.find((item) => item.id === values.patientId);
    const provider = eligibleProviders.find((item) => item.id === values.providerId);
    const result = await onSubmit({
      title: values.title,
      patientId: values.patientId,
      providerId: values.providerId,
      patientName: patient ? `${patient.firstName} ${patient.lastName}`.trim() : plan?.patientName,
      providerName: provider?.name || plan?.providerName,
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
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="treatment-patient-search"
                  value={patientSearch}
                  onChange={(event) => setPatientSearch(event.target.value)}
                  placeholder="Search active patients by name, email, or phone…"
                  className="pl-9"
                />
              </div>
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
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={patientsLoading && displayPatients.length === 0}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            patientsLoading && displayPatients.length === 0
                              ? 'Loading active patients…'
                              : 'Select patient'
                          }
                        />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent className="max-h-64 overflow-y-auto">
                      {patientsLoading && displayPatients.length === 0 ? (
                        <div className="py-6 px-3 text-center text-xs text-muted-foreground">
                          Loading patients…
                        </div>
                      ) : displayPatients.length === 0 ? (
                        <div className="py-6 px-3 text-center text-xs text-muted-foreground">
                          No active patients found{debouncedSearch ? ` matching "${debouncedSearch}"` : ''}
                        </div>
                      ) : (
                        displayPatients.map((patient) => (
                          <SelectItem key={patient.id} value={patient.id}>
                            <div className="flex flex-col text-left py-0.5">
                              <span className="font-medium text-foreground">
                                {patient.firstName} {patient.lastName}
                              </span>
                              {(patient.phone || patient.email) && (
                                <span className="text-xs text-muted-foreground">
                                  {[patient.phone, patient.email].filter(Boolean).join(' • ')}
                                </span>
                              )}
                            </div>
                          </SelectItem>
                        ))
                      )}
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
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={providersLoading && eligibleProviders.length === 0}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            providersLoading && eligibleProviders.length === 0
                              ? 'Loading providers…'
                              : 'Select provider'
                          }
                        />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent className="max-h-60 overflow-y-auto">
                      {providersLoading && eligibleProviders.length === 0 ? (
                        <div className="py-4 text-center text-xs text-muted-foreground">
                          Loading providers…
                        </div>
                      ) : eligibleProviders.length === 0 ? (
                        <div className="py-4 text-center text-xs text-muted-foreground">
                          No providers available
                        </div>
                      ) : (
                        eligibleProviders.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            {provider.name}
                          </SelectItem>
                        ))
                      )}
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
