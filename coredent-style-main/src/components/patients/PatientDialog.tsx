// ============================================
// Patient Dialog Component
// Create and edit patient records
// ============================================

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { CalendarIcon, Plus, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/auth-context';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { patientApi } from '@/services/patientApi';
import { triggerAutomation } from '@/services/automationApi';
import { useToast } from '@/hooks/use-toast';
import { logger } from '@/lib/logger';
import type { PatientRecord, PatientFormData } from '@/types/patient';
import { defaultMedicalHistory, defaultDentalHistory } from '@/types/patient';
import { US_STATES } from '@/types/clinic';

const patientSchema = z.object({
  firstName: z.string().min(1, 'First name is required').max(50),
  lastName: z.string().min(1, 'Last name is required').max(50),
  dateOfBirth: z.date({ required_error: 'Date of birth is required' }),
  gender: z.enum(['male', 'female', 'other']),
  email: z.string().email('Invalid email address'),
  phone: z.string().min(10, 'Phone number is required'),
  street: z.string().min(1, 'Street address is required'),
  city: z.string().min(1, 'City is required'),
  state: z.string().min(2, 'State is required'),
  zipCode: z.string().min(5, 'ZIP code is required'),
  emergencyName: z.string().min(1, 'Emergency contact name is required'),
  emergencyRelationship: z.string().min(1, 'Relationship is required'),
  emergencyPhone: z.string().min(10, 'Emergency contact phone is required'),
});

type FormData = z.infer<typeof patientSchema>;

interface PatientDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patient?: PatientRecord | null;
  onSave: () => void;
  region: string;
}

export function PatientDialog({
  open,
  onOpenChange,
  patient,
  onSave,
  region,
}: PatientDialogProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const clinicName = user?.practiceName?.trim() || 'Your dental clinic';
  const [activeTab, setActiveTab] = useState('basic');
  const [isSaving, setIsSaving] = useState(false);
  const [medicalAlerts, setMedicalAlerts] = useState<string[]>([]);
  const [newAlert, setNewAlert] = useState('');

  const isEditing = !!patient;

  const form = useForm<FormData>({
    resolver: zodResolver(patientSchema),
    defaultValues: {
      firstName: '',
      lastName: '',
      gender: 'male',
      email: '',
      phone: '',
      street: '',
      city: '',
      state: '',
      zipCode: '',
      emergencyName: '',
      emergencyRelationship: '',
      emergencyPhone: '',
    },
  });

  useEffect(() => {
    if (open) {
      if (patient) {
        form.reset({
          firstName: patient.firstName,
          lastName: patient.lastName,
          dateOfBirth: new Date(patient.dateOfBirth),
          gender: patient.gender,
          email: patient.email,
          phone: patient.phone,
          street: patient.address.street,
          city: patient.address.city,
          state: patient.address.state,
          zipCode: patient.address.zipCode,
          emergencyName: patient.emergencyContact.name,
          emergencyRelationship: patient.emergencyContact.relationship,
          emergencyPhone: patient.emergencyContact.phone,
        });
        setMedicalAlerts(patient.medicalAlerts);
      } else {
        form.reset({
          firstName: '',
          lastName: '',
          gender: 'male',
          email: '',
          phone: '',
          street: '',
          city: '',
          state: '',
          zipCode: '',
          emergencyName: '',
          emergencyRelationship: '',
          emergencyPhone: '',
        });
        setMedicalAlerts([]);
      }
      setActiveTab('basic');
    }
  }, [open, patient, form]);

  const addMedicalAlert = () => {
    if (newAlert.trim() && !medicalAlerts.includes(newAlert.trim())) {
      setMedicalAlerts([...medicalAlerts, newAlert.trim()]);
      setNewAlert('');
    }
  };

  const removeMedicalAlert = (alert: string) => {
    setMedicalAlerts(medicalAlerts.filter(a => a !== alert));
  };

  const onSubmit = async (data: FormData) => {
    setIsSaving(true);
    try {
      const patientData: PatientFormData = {
        firstName: data.firstName,
        lastName: data.lastName,
        dateOfBirth: format(data.dateOfBirth, 'yyyy-MM-dd'),
        gender: data.gender,
        email: data.email,
        phone: data.phone,
        address: {
          street: data.street,
          city: data.city,
          state: data.state,
          zipCode: data.zipCode,
        },
        emergencyContact: {
          name: data.emergencyName,
          relationship: data.emergencyRelationship,
          phone: data.emergencyPhone,
        },
        medicalAlerts,
        medicalHistory: patient?.medicalHistory || defaultMedicalHistory,
        dentalHistory: patient?.dentalHistory || defaultDentalHistory,
      };

      if (isEditing) {
        await patientApi.updatePatient(patient.id, patientData);
      } else {
        const newPatient = await patientApi.createPatient(patientData);
        // Trigger patient_registered automation (fire-and-forget: the save
        // already succeeded, a webhook failure must not reject the save)
        Promise.resolve(triggerAutomation('patient_registered', {
          patientId: newPatient?.id || '',
          patientName: `${data.firstName} ${data.lastName}`,
          patientPhone: data.phone,
          patientEmail: data.email,
          clinicName,
        })).catch((automationError) => {
          logger.warn('patient_registered automation failed', {
            error: automationError instanceof Error ? automationError.message : String(automationError),
          });
        });
      }
      onSave();
    } catch (error) {
      // Surface the failure — silently swallowing it left the user with no
      // idea their changes were not persisted.
      toast({
        title: 'Error',
        description:
          error instanceof Error
            ? error.message
            : `Failed to ${isEditing ? 'update' : 'create'} patient. Please try again.`,
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Edit Patient' : 'New Patient'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid grid-cols-3 w-full">
              <TabsTrigger value="basic">Basic Info</TabsTrigger>
              <TabsTrigger value="contact">Contact</TabsTrigger>
              <TabsTrigger value="medical">Medical</TabsTrigger>
            </TabsList>

            <ScrollArea className="h-[400px] mt-4 pr-4">
              <TabsContent value="basic" className="space-y-4 mt-0">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="firstName">First Name *</Label>
                    <Input
                      id="firstName"
                      {...form.register('firstName')}
                      placeholder="John"
                      aria-invalid={!!form.formState.errors.firstName}
                      aria-describedby={form.formState.errors.firstName ? 'firstName-error' : undefined}
                    />
                    {form.formState.errors.firstName && (
                      <p id="firstName-error" role="alert" className="text-sm text-destructive">
                        {form.formState.errors.firstName.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lastName">Last Name *</Label>
                    <Input
                      id="lastName"
                      {...form.register('lastName')}
                      placeholder="Smith"
                      aria-invalid={!!form.formState.errors.lastName}
                      aria-describedby={form.formState.errors.lastName ? 'lastName-error' : undefined}
                    />
                    {form.formState.errors.lastName && (
                      <p id="lastName-error" role="alert" className="text-sm text-destructive">
                        {form.formState.errors.lastName.message}
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Date of Birth *</Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className={cn(
                            "w-full justify-start text-left font-normal",
                            !form.watch('dateOfBirth') && "text-muted-foreground"
                          )}
                          aria-describedby={form.formState.errors.dateOfBirth ? 'dateOfBirth-error' : undefined}
                        >
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {form.watch('dateOfBirth') 
                            ? format(form.watch('dateOfBirth'), 'PPP')
                            : 'Select date'
                          }
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={form.watch('dateOfBirth')}
                          onSelect={(date) => date && form.setValue('dateOfBirth', date)}
                          disabled={(date) => date > new Date()}
                          initialFocus
                          className={cn("p-3 pointer-events-auto")}
                        />
                      </PopoverContent>
                    </Popover>
                    {form.formState.errors.dateOfBirth && (
                      <p id="dateOfBirth-error" role="alert" className="text-sm text-destructive">
                        {form.formState.errors.dateOfBirth.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label>Gender *</Label>
                    <Select
                      value={form.watch('gender')}
                      onValueChange={(value) => form.setValue('gender', value as FormData['gender'])}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select gender" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="male">Male</SelectItem>
                        <SelectItem value="female">Female</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      {...form.register('email')}
                      placeholder="john@example.com"
                      aria-invalid={!!form.formState.errors.email}
                      aria-describedby={form.formState.errors.email ? 'email-error' : undefined}
                    />
                    {form.formState.errors.email && (
                      <p id="email-error" role="alert" className="text-sm text-destructive">
                        {form.formState.errors.email.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone *</Label>
                    <Input
                      id="phone"
                      {...form.register('phone')}
                      placeholder={region === 'IN' ? '+91 XXXX-XXXXXX' : '(555) 123-4567'}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="contact" className="space-y-4 mt-0">
                <h4 className="font-medium">Address</h4>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="street">Street Address *</Label>
                    <Input
                      id="street"
                      {...form.register('street')}
                      placeholder="123 Main Street"
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="city">City *</Label>
                      <Input
                        id="city"
                        {...form.register('city')}
                        placeholder="Los Angeles"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>State *</Label>
                      <Select
                        value={form.watch('state')}
                        onValueChange={(v) => form.setValue('state', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="State" />
                        </SelectTrigger>
                        <SelectContent>
                          {US_STATES.map((state) => (
                            <SelectItem key={state.code} value={state.code}>
                              {state.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="zipCode">ZIP Code *</Label>
                      <Input
                        id="zipCode"
                        {...form.register('zipCode')}
                        placeholder="90001"
                      />
                    </div>
                  </div>
                </div>

                <h4 className="font-medium pt-4">Emergency Contact</h4>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="emergencyName">Name *</Label>
                      <Input
                        id="emergencyName"
                        {...form.register('emergencyName')}
                        placeholder="Jane Doe"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="emergencyRelationship">Relationship *</Label>
                      <Input
                        id="emergencyRelationship"
                        {...form.register('emergencyRelationship')}
                        placeholder="Spouse"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="emergencyPhone">Phone *</Label>
                    <Input
                      id="emergencyPhone"
                      {...form.register('emergencyPhone')}
                      placeholder="(555) 999-8888"
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="medical" className="space-y-4 mt-0">
                <h4 className="font-medium">Medical Alerts</h4>
                <p className="text-sm text-muted-foreground">
                  Add important medical alerts that staff should be aware of (allergies, conditions, etc.)
                </p>
                
                <div className="flex gap-2">
                  <Input
                    value={newAlert}
                    onChange={(e) => setNewAlert(e.target.value)}
                    placeholder="e.g., Penicillin Allergy"
                    aria-label="New medical alert"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addMedicalAlert();
                      }
                    }}
                  />
                  <Button type="button" onClick={addMedicalAlert} size="icon" aria-label="Add medical alert">
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {medicalAlerts.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {medicalAlerts.map((alert) => (
                      <Badge 
                        key={alert} 
                        variant="destructive"
                        className="gap-1 pr-1"
                      >
                        {alert}
                        <button
                          type="button"
                          onClick={() => removeMedicalAlert(alert)}
                          className="ml-1 hover:bg-destructive-foreground/20 rounded-full p-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}

                <p className="text-sm text-muted-foreground pt-4">
                  Additional medical and dental history can be added after creating the patient record.
                </p>
              </TabsContent>
            </ScrollArea>
          </Tabs>

          <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : isEditing ? 'Update Patient' : 'Create Patient'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
