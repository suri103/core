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
import type { ReferralRecord } from '@/services/referralsApi';

const REFERRAL_TYPES = [
  'oral_surgery', 'endodontics', 'periodontics', 'orthodontics', 'prosthodontics',
  'pediatric', 'implant', 'cosmetic', 'emergency', 'consultation', 'other',
];

const REFERRAL_STATUSES = ['pending', 'sent', 'scheduled', 'completed', 'cancelled', 'no_show'];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: ReferralRecord | null;
  onSubmit: (data: {
    patient_id: string;
    referral_type?: string;
    status?: string;
    reason?: string;
    notes?: string;
    referral_fee?: string | number;
    urgency?: string;
  }) => Promise<boolean>;
}

export function NewReferralDialog({ open, onOpenChange, initial, onSubmit }: Props) {
  const { data: patientsResponse } = useQuery({
    queryKey: ['patients', 'list-simple'],
    queryFn: () => patientsApi.list({ limit: 100 }),
    enabled: open,
  });
  const patients = patientsResponse?.data?.data ?? [];

  const [patientId, setPatientId] = useState('');
  const [type, setType] = useState('');
  const [status, setStatus] = useState('pending');
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [fee, setFee] = useState('');
  const [urgency, setUrgency] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (initial) {
        setPatientId(initial.patient_id ?? '');
        setType(initial.referral_type ?? '');
        setStatus(initial.status ?? 'pending');
        setReason(initial.reason ?? '');
        setNotes(initial.notes ?? '');
        setFee(initial.referral_fee != null ? String(initial.referral_fee) : '');
        setUrgency(initial.urgency ?? '');
      } else {
        setPatientId(''); setType(''); setStatus('pending');
        setReason(''); setNotes(''); setFee(''); setUrgency('');
      }
    }
  }, [open, initial]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId) return;
    setIsSubmitting(true);
    try {
      const ok = await onSubmit({
        patient_id: patientId,
        referral_type: type || undefined,
        status,
        reason: reason || undefined,
        notes: notes || undefined,
        referral_fee: fee ? Number(fee) : undefined,
        urgency: urgency || undefined,
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
          <DialogTitle>{initial ? 'Edit Referral' : 'New Referral'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
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
              <Label>Type</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                <SelectContent>
                  {REFERRAL_TYPES.map((t) => (
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
                  {REFERRAL_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Fee ($)</Label>
              <Input type="number" min="0" step="0.01" value={fee} onChange={(e) => setFee(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Urgency</Label>
              <Select value={urgency} onValueChange={setUrgency}>
                <SelectTrigger><SelectValue placeholder="Select urgency" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Reason</Label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting || !patientId}>
              {isSubmitting ? 'Saving…' : (initial ? 'Save Changes' : 'Create Referral')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
