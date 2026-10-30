/**
 * AppointmentForm Component
 * Form for creating/editing appointments
 *
 * This is the single canonical appointment form. The Appointments page and
 * any scheduling dialog reuse it so status casing, duration handling, and
 * field behavior cannot drift between copies.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DialogFooter } from '@/components/ui/dialog';
import type { Appointment } from '@/services/appointmentsApi';

interface AppointmentType {
  id: string;
  name: string;
  duration: number;
}

interface AppointmentFormProps {
  appointment?: Appointment | null;
  appointmentTypes?: AppointmentType[];
  onSubmit?: (data: Partial<Appointment>) => void;
  onCancel?: () => void;
}

/**
 * Strip display suffixes (e.g. "30 min") so the number input holds a
 * numeric value the browser will accept for form validation.
 */
const toNumericDuration = (value?: string | number): string => {
  const raw = String(value ?? '').replace(/\D/g, '');
  return raw ? raw : '30';
};

/**
 * Form for creating and editing appointments
 */
export const AppointmentForm = React.memo(function AppointmentForm({
  appointment,
  appointmentTypes = [],
  onSubmit,
  onCancel,
}: AppointmentFormProps) {
  const [formData, setFormData] = useState<Partial<Appointment>>(
    appointment
      ? { ...appointment, duration: toNumericDuration(appointment.duration) }
      : {
          patient: '',
          patientName: '',
          time: '',
          duration: '30',
          type: '',
          dentist: '',
          status: 'scheduled',
          patientId: '',
          providerId: '',
          operatoryId: '',
        }
  );

  // Reset form when appointment changes
  useEffect(() => {
    if (appointment) {
      setFormData({
        ...appointment,
        duration: toNumericDuration(appointment.duration),
      });
    }
  }, [appointment]);

  const handleChange = (field: keyof Appointment, value: string) => {
    setFormData((prev) => {
      const next = { ...prev, [field]: value };
      // Keep the display name and the wire name in sync so the API adapter
      // (which resolves patients by `patientName`) always sees the same value.
      if (field === 'patient') next.patientName = value;
      if (field === 'patientName') next.patient = value;
      return next;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit?.(formData);
  };

  return (
    <form onSubmit={handleSubmit} data-testid="appointment-form" className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="patient">Patient Name</Label>
        <Input
          id="patient"
          value={formData.patient || ''}
          onChange={(e) => handleChange('patient', e.target.value)}
          placeholder="Enter patient name"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="time">Time</Label>
        <Input
          id="time"
          value={formData.time || ''}
          onChange={(e) => handleChange('time', e.target.value)}
          placeholder="e.g., 9:00 AM"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="duration">Duration (minutes)</Label>
        <Input
          id="duration"
          type="number"
          value={formData.duration || '30'}
          onChange={(e) => handleChange('duration', e.target.value)}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="type">Appointment Type</Label>
        <Select
          value={formData.type || ''}
          onValueChange={(value) => handleChange('type', value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select type" />
          </SelectTrigger>
          <SelectContent>
            {appointmentTypes.map((type) => (
              <SelectItem key={type.id} value={type.name}>
                {type.name} ({type.duration} min)
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="dentist">Dentist</Label>
        <Input
          id="dentist"
          value={formData.dentist || ''}
          onChange={(e) => handleChange('dentist', e.target.value)}
          placeholder="e.g., Dr. Wilson"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="status">Status</Label>
        <Select
          value={formData.status || 'scheduled'}
          onValueChange={(value) => handleChange('status', value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select status" />
          </SelectTrigger>
          <SelectContent>
            {/* Values are the backend enum (lowercase); labels are human-friendly. */}
            <SelectItem value="scheduled">Pending</SelectItem>
            <SelectItem value="confirmed">Confirmed</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="patientId">Patient ID</Label>
        <Input
          id="patientId"
          value={formData.patientId || ''}
          onChange={(e) => handleChange('patientId', e.target.value)}
          placeholder="Patient UUID (optional — resolved by name otherwise)"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="providerId">Provider ID</Label>
        <Input
          id="providerId"
          value={formData.providerId || ''}
          onChange={(e) => handleChange('providerId', e.target.value)}
          placeholder="Provider UUID (optional)"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="operatoryId">Operatory ID</Label>
        <Input
          id="operatoryId"
          value={formData.operatoryId || ''}
          onChange={(e) => handleChange('operatoryId', e.target.value)}
          placeholder="Operatory/chair UUID (optional)"
        />
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          {appointment ? 'Update' : 'Create'} Appointment
        </Button>
      </DialogFooter>
    </form>
  );
});
