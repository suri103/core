import React, { useState, useEffect } from 'react';
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
import { Checkbox } from '@/components/ui/checkbox';
import type { ReferralSourceRecord } from '@/services/referralsApi';

const SOURCE_TYPES = [
  'patient', 'insurance', 'friend', 'physician', 'other_dentist', 'marketing', 'other',
];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: ReferralSourceRecord | null;
  onSubmit: (data: {
    name: string;
    source_type?: string;
    contact_name?: string;
    email?: string;
    phone?: string;
    specialty?: string;
    is_active?: boolean;
    notes?: string;
  }) => Promise<boolean>;
}

export function NewReferralSourceDialog({ open, onOpenChange, initial, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [contact, setContact] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [active, setActive] = useState(true);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (initial) {
        setName(initial.name ?? '');
        setSourceType(initial.source_type ?? '');
        setContact(initial.contact_name ?? '');
        setEmail(initial.email ?? '');
        setPhone(initial.phone ?? '');
        setSpecialty(initial.specialty ?? '');
        setActive(initial.is_active ?? true);
        setNotes(initial.notes ?? '');
      } else {
        setName(''); setSourceType(''); setContact(''); setEmail('');
        setPhone(''); setSpecialty(''); setActive(true); setNotes('');
      }
    }
  }, [open, initial]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      const ok = await onSubmit({
        name: name.trim(),
        source_type: sourceType || undefined,
        contact_name: contact.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        specialty: specialty.trim() || undefined,
        is_active: active,
        notes: notes.trim() || undefined,
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
          <DialogTitle>{initial ? 'Edit Referral Source' : 'Add Referral Source'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label>Source Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Dr. Smith Oral Surgery" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={sourceType} onValueChange={setSourceType}>
                <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                <SelectContent>
                  {SOURCE_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Specialty</Label>
              <Input value={specialty} onChange={(e) => setSpecialty(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Contact Name</Label>
              <Input value={contact} onChange={(e) => setContact(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Phone</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <label className="flex items-center gap-2">
            <Checkbox checked={active} onCheckedChange={(v) => setActive(!!v)} />
            <span className="text-sm">Active</span>
          </label>
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting || !name.trim()}>
              {isSubmitting ? 'Saving…' : (initial ? 'Save Changes' : 'Add Source')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
