// ============================================
// Schedule Page
// Main appointment scheduling interface
// ============================================

import { useEffect, useState, useCallback } from 'react';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { ScheduleHeader } from '@/components/scheduling/ScheduleHeader';
import { DayView } from '@/components/scheduling/DayView';
import { WeekView } from '@/components/scheduling/WeekView';
import { MonthView } from '@/components/scheduling/MonthView';
import { AppointmentDialog } from '@/components/scheduling/AppointmentDialog';
import { AppointmentDetailsSheet } from '@/components/scheduling/AppointmentDetailsSheet';
import { PatientSearchDialog } from '@/components/scheduling/PatientSearchDialog';
import { useScheduling } from '@/hooks/useScheduling';
import { schedulingApi } from '@/services/schedulingApi';
import { triggerAutomation } from '@/services/automationApi';
import type { ScheduleAppointment, AppointmentFormData, PatientSearchResult } from '@/types/scheduling';
import type { AppointmentStatus } from '@/types/api';
import { parseTimeString } from '@/types/scheduling';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertTriangle } from 'lucide-react';
import { logger } from '@/lib/logger';

// Fire-and-forget automation triggers: the clinical action already succeeded,
// so a webhook failure must not surface as an unhandled rejection. Log it and
// move on.
const fireAutomation = (
  event: Parameters<typeof triggerAutomation>[0],
  payload: Parameters<typeof triggerAutomation>[1],
) => {
  Promise.resolve(triggerAutomation(event, payload)).catch((err) => {
    logger.warn(`${event} automation failed`, {
      error: err instanceof Error ? err.message : String(err),
    });
  });
};

export default function Schedule() {
  const { toast } = useToast();
  const { hasRole, user } = useAuth();
  // Automation payloads previously hardcoded 'CoreDent Clinic'; use the
  // signed-in practice name with a neutral fallback.
  const clinicName = user?.practiceName?.trim() || 'Your dental clinic';
  
  // Check if user can edit appointments
  const canEdit = hasRole('owner', 'admin', 'front_desk');

  const {
    currentDate,
    view,
    appointments,
    chairs,
    providers,
    appointmentTypes,
    isLoading,
    error,
    selectedAppointment,
    formattedDate,
    setView,
    setSelectedAppointment,
    goToToday,
    goToPrevious,
    goToNext,
    goToDate,
    loadData,
    addAppointment,
    updateAppointment,
  } = useScheduling();

  // Dialog states
  const [isAppointmentDialogOpen, setIsAppointmentDialogOpen] = useState(false);
  const [isDetailsSheetOpen, setIsDetailsSheetOpen] = useState(false);
  const [isPatientSearchOpen, setIsPatientSearchOpen] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<ScheduleAppointment | null>(null);
  const [selectedPatientForNew, setSelectedPatientForNew] = useState<PatientSearchResult | null>(null);

  // effect:audited — Load data on mount and when date changes
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle appointment click - show details
  const handleAppointmentClick = useCallback((appointment: ScheduleAppointment) => {
    setSelectedAppointment(appointment);
    setIsDetailsSheetOpen(true);
  }, [setSelectedAppointment]);

  // Handle status change
  const handleStatusChange = useCallback(async (id: string, status: AppointmentStatus) => {
    try {
      await schedulingApi.updateStatus(id, status);
      updateAppointment(id, { status });
      toast({
        title: 'Status Updated',
        description: `Appointment marked as ${status.replace('_', ' ')}`,
      });

      // Trigger automation for status changes
      const appointment = appointments.find(a => a.id === id);
      if (appointment) {
        const payload = {
          appointmentId: id,
          patientName: appointment.patientName,
          appointmentDate: appointment.startTime.toISOString().split('T')[0],
          appointmentTime: appointment.startTime.toLocaleTimeString(),
          providerName: appointment.providerName || '',
          procedureType: appointment.type,
          clinicName,
        };
        if (status === 'confirmed') fireAutomation('appointment_confirmed', payload);
        if (status === 'completed') {
          fireAutomation('appointment_completed', payload);
          fireAutomation('review_request', {
            patientId: appointment.patientId,
            patientName: appointment.patientName,
            appointmentDate: payload.appointmentDate,
            providerName: payload.providerName,
            clinicName,
          });
        }
        if (status === 'no_show') fireAutomation('appointment_no_show', payload);
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to update appointment status',
        variant: 'destructive',
      });
    }
  }, [appointments, updateAppointment, toast]);

  // Handle edit appointment
  const handleEditAppointment = useCallback((appointment: ScheduleAppointment) => {
    setEditingAppointment(appointment);
    setIsDetailsSheetOpen(false);
    setIsAppointmentDialogOpen(true);
  }, []);

  // Handle cancel appointment
  const handleCancelAppointment = useCallback(async (id: string) => {
    try {
      await schedulingApi.cancelAppointment(id);
      updateAppointment(id, { status: 'cancelled' });
      setIsDetailsSheetOpen(false);
      toast({
        title: 'Appointment Cancelled',
        description: 'The appointment has been cancelled',
      });

      // Trigger appointment_cancelled automation
      const appointment = appointments.find(a => a.id === id);
      if (appointment) {
        fireAutomation('appointment_cancelled', {
          appointmentId: id,
          patientName: appointment.patientName,
          appointmentDate: appointment.startTime.toISOString().split('T')[0],
          appointmentTime: appointment.startTime.toLocaleTimeString(),
          providerName: appointment.providerName || '',
          procedureType: appointment.type,
          clinicName,
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to cancel appointment',
        variant: 'destructive',
      });
    }
  }, [appointments, updateAppointment, toast]);

  // Handle new appointment
  const handleNewAppointment = useCallback(() => {
    setEditingAppointment(null);
    setSelectedPatientForNew(null);
    setIsAppointmentDialogOpen(true);
  }, []);

  // Handle save appointment
  const handleSaveAppointment = useCallback(async (data: AppointmentFormData) => {
    if (editingAppointment) {
      // schedulingApi.updateAppointment throws on failure (it used to return
      // null, which this handler ignored and toasted success anyway).
      await schedulingApi.updateAppointment(editingAppointment.id, data);
      const { hours, minutes } = parseTimeString(data.startTime);
      const startTime = new Date(data.date);
      startTime.setHours(hours, minutes, 0, 0);
      const endTime = new Date(startTime.getTime() + data.duration * 60 * 1000);

      updateAppointment(editingAppointment.id, {
        patientId: data.patientId,
        patientName: data.patientName,
        providerId: data.providerId,
        chairId: data.chairId,
        type: data.type,
        startTime,
        endTime,
        duration: data.duration,
        notes: data.notes,
      });
      toast({
        title: 'Appointment Updated',
        description: 'The appointment has been updated successfully',
      });
      return;
    }

    const newAppointment = await schedulingApi.createAppointment(data);
    addAppointment(newAppointment);
    toast({
      title: 'Appointment Created',
      description: `Appointment scheduled for ${data.patientName}`,
    });

    Promise.resolve(
      triggerAutomation('appointment_booked', {
        appointmentId: newAppointment.id,
        patientName: data.patientName,
        appointmentDate: data.date.toISOString().split('T')[0],
        appointmentTime: data.startTime,
        providerName: newAppointment.providerName || '',
        procedureType: data.type,
        clinicName,
      }),
    ).catch((automationError) => {
      logger.warn('appointment_booked automation failed', {
        error: automationError instanceof Error ? automationError.message : String(automationError),
      });
    });  }, [editingAppointment, updateAppointment, addAppointment, toast]);

  // Handle drag-and-drop reschedule (Day View)
  const handleDropAppointmentDay = useCallback(async (appointmentId: string, chairId: string, time: string) => {
    try {
      const appointment = appointments.find(a => a.id === appointmentId);
      if (!appointment) return;

      const { hours, minutes } = parseTimeString(time);
      const newStartTime = new Date(currentDate);
      newStartTime.setHours(hours, minutes, 0, 0);
      const newEndTime = new Date(newStartTime.getTime() + appointment.duration * 60 * 1000);

      await schedulingApi.rescheduleAppointment(appointmentId, chairId, newStartTime);
      
      const chair = chairs.find(c => c.id === chairId);
      updateAppointment(appointmentId, {
        chairId,
        chairName: chair?.name || '',
        startTime: newStartTime,
        endTime: newEndTime,
      });

      toast({
        title: 'Appointment Rescheduled',
        description: `Moved to ${chair?.name || 'new location'}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to reschedule appointment',
        variant: 'destructive',
      });
    }
  }, [appointments, currentDate, chairs, updateAppointment, toast]);

  // Handle drag-and-drop reschedule (Week View)
  const handleDropAppointmentWeek = useCallback(async (appointmentId: string, date: Date, time: string) => {
    try {
      const appointment = appointments.find(a => a.id === appointmentId);
      if (!appointment) return;

      const { hours, minutes } = parseTimeString(time);
      const newStartTime = new Date(date);
      newStartTime.setHours(hours, minutes, 0, 0);
      const newEndTime = new Date(newStartTime.getTime() + appointment.duration * 60 * 1000);

      await schedulingApi.rescheduleAppointment(appointmentId, appointment.chairId, newStartTime);
      
      updateAppointment(appointmentId, {
        startTime: newStartTime,
        endTime: newEndTime,
      });

      toast({
        title: 'Appointment Rescheduled',
        description: 'Appointment moved successfully',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to reschedule appointment',
        variant: 'destructive',
      });
    }
  }, [appointments, updateAppointment, toast]);

  // Handle day click from week/month view
  const handleDayClick = useCallback((date: Date) => {
    goToDate(date);
    setView('day');
  }, [goToDate, setView]);

  // Handle patient select from search
  const handlePatientSelect = useCallback((patient: PatientSearchResult) => {
    setSelectedPatientForNew(patient);
    setIsPatientSearchOpen(false);
    setIsAppointmentDialogOpen(true);
  }, []);

  if (isLoading && appointments.length === 0) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <ScheduleHeader
        formattedDate={formattedDate}
        currentDate={currentDate}
        view={view}
        onViewChange={setView}
        onPrevious={goToPrevious}
        onNext={goToNext}
        onToday={goToToday}
        onDateSelect={goToDate}
        onNewAppointment={handleNewAppointment}
        onOpenSearch={() => setIsPatientSearchOpen(true)}
      />

      {error && (
        <Alert variant="destructive" role="alert" className="mt-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Schedule data unavailable</AlertTitle>
          <AlertDescription>
            {error.message}. Existing schedule data is preserved; retry after the service recovers.
          </AlertDescription>
        </Alert>
      )}

      <div className="flex-1 mt-4 overflow-hidden border rounded-lg bg-card">
        {view === 'day' && (
          <DayView
            date={currentDate}
            chairs={chairs}
            appointments={appointments}
            onAppointmentClick={handleAppointmentClick}
            onStatusChange={handleStatusChange}
            onEditAppointment={handleEditAppointment}
            onCancelAppointment={handleCancelAppointment}
            onDropAppointment={handleDropAppointmentDay}
            canEdit={canEdit}
          />
        )}

        {view === 'week' && (
          <WeekView
            currentDate={currentDate}
            appointments={appointments}
            onAppointmentClick={handleAppointmentClick}
            onStatusChange={handleStatusChange}
            onEditAppointment={handleEditAppointment}
            onCancelAppointment={handleCancelAppointment}
            onDropAppointment={handleDropAppointmentWeek}
            onDayClick={handleDayClick}
            canEdit={canEdit}
          />
        )}

        {view === 'month' && (
          <MonthView
            currentDate={currentDate}
            appointments={appointments}
            onDayClick={handleDayClick}
            onAppointmentClick={handleAppointmentClick}
          />
        )}
      </div>

      {/* Appointment Create/Edit Dialog */}
      <AppointmentDialog
        open={isAppointmentDialogOpen}
        onOpenChange={setIsAppointmentDialogOpen}
        appointment={editingAppointment}
        selectedPatient={selectedPatientForNew}
        chairs={chairs}
        providers={providers}
        appointmentTypes={appointmentTypes}
        defaultDate={currentDate}
        onSave={handleSaveAppointment}
      />

      {/* Appointment Details Sheet */}
      <AppointmentDetailsSheet
        open={isDetailsSheetOpen}
        onOpenChange={setIsDetailsSheetOpen}
        appointment={selectedAppointment}
        onEdit={() => selectedAppointment && handleEditAppointment(selectedAppointment)}
        onStatusChange={(status: AppointmentStatus) => selectedAppointment && handleStatusChange(selectedAppointment.id, status)}
        onCancel={() => selectedAppointment && handleCancelAppointment(selectedAppointment.id)}
        canEdit={canEdit}
      />

      {/* Patient Search Dialog */}
      <PatientSearchDialog
        open={isPatientSearchOpen}
        onOpenChange={setIsPatientSearchOpen}
        onSelectPatient={handlePatientSelect}
      />
    </div>
  );
}
