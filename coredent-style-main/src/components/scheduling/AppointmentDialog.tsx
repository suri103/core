import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { schedulingApi } from '@/services/schedulingApi';
import type { ScheduleAppointment, AppointmentFormData, PatientSearchResult, ScheduleProvider } from '@/types/scheduling';
import type { Chair, AppointmentTypeConfig } from '@/types/clinic';
import { Search, User, Loader2 } from 'lucide-react';

interface AppointmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointment: ScheduleAppointment | null;
  selectedPatient?: PatientSearchResult | null;
  chairs: Chair[];
  providers: ScheduleProvider[];
  appointmentTypes: AppointmentTypeConfig[];
  defaultDate: Date;
  onSave: (data: AppointmentFormData) => Promise<void>;
}

export function AppointmentDialog({
  open,
  onOpenChange,
  appointment,
  selectedPatient,
  chairs,
  providers,
  appointmentTypes,
  defaultDate,
  onSave,
}: AppointmentDialogProps) {
  const { toast } = useToast();

  // Form State
  const [patientId, setPatientId] = useState('');
  const [patientName, setPatientName] = useState('');
  const [providerId, setProviderId] = useState('');
  const [chairId, setChairId] = useState('');
  const [type, setType] = useState('');
  const [date, setDate] = useState('');
  const [startTime, setStartTime] = useState('09:00');
  const [duration, setDuration] = useState(30);
  const [notes, setNotes] = useState('');

  // Inline Patient Search State
  const [patientQuery, setPatientQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchResults, setSearchResults] = useState<PatientSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load defaults or edit values
  useEffect(() => {
    if (!open) return;

    if (appointment) {
      // Edit mode
      setPatientId(appointment.patientId);
      setPatientName(appointment.patientName);
      setPatientQuery(appointment.patientName);
      setProviderId(appointment.providerId);
      setChairId(appointment.chairId);
      setType(appointment.type);
      setNotes(appointment.notes || '');
      setDuration(appointment.duration);
      
      // Format date to YYYY-MM-DD
      const dateObj = appointment.startTime;
      const year = dateObj.getFullYear();
      const month = String(dateObj.getMonth() + 1).padStart(2, '0');
      const day = String(dateObj.getDate()).padStart(2, '0');
      setDate(`${year}-${month}-${day}`);

      // Format time to HH:MM
      const hours = String(dateObj.getHours()).padStart(2, '0');
      const minutes = String(dateObj.getMinutes()).padStart(2, '0');
      setStartTime(`${hours}:${minutes}`);
    } else {
      // Create mode
      setProviderId(providers[0]?.id || '');
      setChairId(chairs[0]?.id || '');
      setType(appointmentTypes[0]?.name || '');
      setDuration(appointmentTypes[0]?.duration || 30);
      setNotes('');
      setStartTime('09:00');

      // Date formatting
      const year = defaultDate.getFullYear();
      const month = String(defaultDate.getMonth() + 1).padStart(2, '0');
      const day = String(defaultDate.getDate()).padStart(2, '0');
      setDate(`${year}-${month}-${day}`);

      if (selectedPatient) {
        setPatientId(selectedPatient.id);
        setPatientName(selectedPatient.name);
        setPatientQuery(selectedPatient.name);
      } else {
        setPatientId('');
        setPatientName('');
        setPatientQuery('');
      }
    }
  }, [open, appointment, selectedPatient, defaultDate, chairs, providers, appointmentTypes]);

  // Debounced inline patient search
  useEffect(() => {
    // Skip only while a patient is actually selected and the query still
    // matches the selected name. Comparing names when no patient is selected
    // let a stale patientId survive a re-typed identical name.
    if (!patientQuery.trim() || (patientId && patientQuery === patientName)) {
      setSearchResults([]);
      return;
    }

    const delaySearch = setTimeout(async () => {
      setIsSearching(true);
      try {
        const patients = await schedulingApi.searchPatients(patientQuery);
        setSearchResults(patients);
      } catch (error) {
        console.error('Failed inline search', error);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(delaySearch);
    // patientId is read inside the guard, so it belongs in the dependency list
    // (L-04): without it a stale patientId could survive a re-typed query.
  }, [patientQuery, patientName, patientId]);

  // Handle appointment type change -> update default duration
  const handleTypeChange = (val: string) => {
    setType(val);
    const matchedType = appointmentTypes.find(t => t.name === val || t.id === val);
    if (matchedType) {
      setDuration(matchedType.duration);
    }
  };

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId || !date || !startTime || !providerId || !chairId || !type) return;

    setIsSubmitting(true);
    try {
      const parsedDate = new Date(date + 'T00:00:00');
      const formData: AppointmentFormData = {
        patientId,
        patientName,
        providerId,
        chairId,
        type,
        date: parsedDate,
        startTime,
        duration: Number(duration),
        notes: notes || undefined,
      };
      await onSave(formData);
      onOpenChange(false);
    } catch (error) {
      // Surface the failure — previously the dialog silently stopped at
      // "Saving..." with no indication the appointment was not saved.
      toast({
        title: 'Error',
        description:
          error instanceof Error
            ? error.message
            : 'Failed to save appointment. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{appointment ? 'Edit Appointment' : 'New Appointment'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {/* Patient Selection */}
          <div className="space-y-2 relative">
            <Label htmlFor="patient">Patient</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="patient"
                placeholder="Search patient to select..."
                value={patientQuery}
                onChange={(e) => {
                  setPatientQuery(e.target.value);
                  if (patientId) {
                    setPatientId('');
                    setPatientName('');
                  }
                }}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setTimeout(() => setSearchFocused(false), 200)}
                className="pl-9"
                required
                disabled={!!appointment}
              />
            </div>
            
            {/* Suggestions Dropdown */}
            {searchFocused && (patientQuery.trim() !== patientName) && (
              <div className="absolute z-50 w-full bg-popover text-popover-foreground border rounded-md shadow-md max-h-[180px] overflow-y-auto mt-1 py-1">
                {isSearching ? (
                  <div className="flex items-center justify-center py-4 text-sm text-muted-foreground gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Searching...</span>
                  </div>
                ) : searchResults.length === 0 ? (
                  <div className="py-3 px-4 text-sm text-muted-foreground text-center">
                    No patients found
                  </div>
                ) : (
                  searchResults.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onMouseDown={() => {
                        setPatientId(p.id);
                        setPatientName(p.name);
                        setPatientQuery(p.name);
                        setSearchResults([]);
                      }}
                      className="w-full text-left px-4 py-2 hover:bg-accent text-sm flex items-center gap-2 cursor-pointer"
                    >
                      <User className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>{p.name}</span>
                      {p.phone && <span className="text-xs text-muted-foreground ml-auto">{p.phone}</span>}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Date */}
            <div className="space-y-2">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </div>

            {/* Start Time */}
            <div className="space-y-2">
              <Label htmlFor="startTime">Start Time</Label>
              <Input
                id="startTime"
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Duration */}
            <div className="space-y-2">
              <Label htmlFor="duration">Duration (Minutes)</Label>
              <Select
                value={String(duration)}
                onValueChange={(val) => setDuration(Number(val))}
              >
                <SelectTrigger id="duration">
                  <SelectValue placeholder="Duration" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15 mins</SelectItem>
                  <SelectItem value="30">30 mins</SelectItem>
                  <SelectItem value="45">45 mins</SelectItem>
                  <SelectItem value="60">60 mins</SelectItem>
                  <SelectItem value="90">90 mins</SelectItem>
                  <SelectItem value="120">120 mins</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Appointment Type */}
            <div className="space-y-2">
              <Label htmlFor="type">Type</Label>
              <Select value={type} onValueChange={handleTypeChange}>
                <SelectTrigger id="type">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {appointmentTypes.map((t) => (
                    <SelectItem key={t.id} value={t.name}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Dentist / Provider */}
            <div className="space-y-2">
              <Label htmlFor="provider">Dentist</Label>
              <Select value={providerId} onValueChange={setProviderId}>
                <SelectTrigger id="provider">
                  <SelectValue placeholder="Select Dentist" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Operatory / Chair */}
            <div className="space-y-2">
              <Label htmlFor="chair">Operatory / Chair</Label>
              <Select value={chairId} onValueChange={setChairId}>
                <SelectTrigger id="chair">
                  <SelectValue placeholder="Select Chair" />
                </SelectTrigger>
                <SelectContent>
                  {chairs.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes">Clinical Notes</Label>
            <Textarea
              id="notes"
              placeholder="Treatment details, symptoms, etc."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !patientId}>
              {isSubmitting ? (
                <span className="flex items-center gap-1">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </span>
              ) : appointment ? (
                'Save Changes'
              ) : (
                'Schedule Appointment'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
