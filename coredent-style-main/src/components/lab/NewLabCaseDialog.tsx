import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { patientsApi } from '@/services/api';
import type { LabVendor, LabCaseRecord } from '@/services/labsApi';

const CASE_TYPES = [
  'crown', 'bridge', 'denture', 'partial', 'implant', 'orthodontic',
  'bleaching_tray', 'night_guard', 'sports_guard', 'other',
];

const CASE_STATUSES = [
  'pending', 'sent', 'in_progress', 'quality_check', 'ready_to_ship',
  'shipped', 'delivered', 'completed', 'on_hold', 'cancelled', 'refused',
];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  labs: LabVendor[];
  initial?: LabCaseRecord | null;
  onSubmit: (data: {
    lab_id: string;
    patient_id: string;
    case_type?: string;
    status?: string;
    description?: string;
    shade?: string;
    teeth_involved?: string;
    sent_date?: string;
    due_date?: string;
    provider_notes?: string;
  }) => Promise<boolean>;
}

function localDateFromISO(value?: string): string {
  if (!value) return '';
  const d = new Date(value);
  return isNaN(d.getTime()) ? value.slice(0, 10) : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function NewLabCaseDialog({ open, onOpenChange, labs, initial, onSubmit }: Props) {
  const { data: patientsResponse } = useQuery({
    queryKey: ['patients', 'list-simple'],
    queryFn: () => patientsApi.list({ limit: 100 }),
    enabled: open,
  });
  const patients = patientsResponse?.data?.data ?? [];

  const [labId, setLabId] = useState('');
  const [patientId, setPatientId] = useState('');
  const [caseType, setCaseType] = useState('');
  const [status, setStatus] = useState('pending');
  const [description, setDescription] = useState('');
  const [shade, setShade] = useState('');
  const [teeth, setTeeth] = useState('');
  const [sentDate, setSentDate] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (initial) {
        setLabId(initial.lab_id ?? '');
        setPatientId(initial.patient_id ?? '');
        setCaseType(initial.case_type ?? '');
        setStatus(initial.status ?? 'pending');
        setDescription(initial.description ?? '');
        setShade(initial.shade ?? '');
        setTeeth(initial.teeth_involved ?? '');
        setSentDate(localDateFromISO(initial.sent_date));
        setDueDate(localDateFromISO(initial.due_date));
        setNotes(initial.provider_notes ?? '');
      } else {
        setLabId('');
        setPatientId('');
        setCaseType('');
        setStatus('pending');
        setDescription('');
        setShade('');
        setTeeth('');
        const today = new Date();
        const pad = (n: number) => String(n).padStart(2, '0');
        setSentDate(`${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`);
        setDueDate('');
        setNotes('');
      }
    }
  }, [open, initial]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!labId || !patientId) return;
    setIsSubmitting(true);
    try {
      const ok = await onSubmit({
        lab_id: labId,
        patient_id: patientId,
        case_type: caseType || undefined,
        status,
        description: description || undefined,
        shade: shade || undefined,
        teeth_involved: teeth || undefined,
        sent_date: sentDate || undefined,
        due_date: dueDate || undefined,
        provider_notes: notes || undefined,
      });
      if (ok) onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{initial ? 'Edit Lab Case' : 'New Lab Case'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Lab *</Label>
              <Select value={labId} onValueChange={setLabId}>
                <SelectTrigger><SelectValue placeholder="Select lab" /></SelectTrigger>
                <SelectContent>
                  {labs.map((l) => (
                    <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Patient *</Label>
              <Select value={patientId} onValueChange={setPatientId}>
                <SelectTrigger><SelectValue placeholder="Select patient" /></SelectTrigger>
                <SelectContent>
                  {patients.map((p) => (
                    <SelectItem key={p.id} value={p.id}>{p.firstName} {p.lastName}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Case Type</Label>
              <Select value={caseType} onValueChange={setCaseType}>
                <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                <SelectContent>
                  {CASE_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CASE_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Sent Date</Label>
              <Input type="date" value={sentDate} onChange={(e) => setSentDate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Due Date</Label>
              <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Shade</Label>
              <Input value={shade} onChange={(e) => setShade(e.target.value)} placeholder="e.g. A2" />
            </div>
            <div className="space-y-1">
              <Label>Teeth Involved</Label>
              <Input value={teeth} onChange={(e) => setTeeth(e.target.value)} placeholder="e.g. 8-10" />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting || !labId || !patientId}>
              {isSubmitting ? 'Saving…' : (initial ? 'Save Changes' : 'Create Case')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
