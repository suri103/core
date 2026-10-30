import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import type { LabVendor } from '@/services/labsApi';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: LabVendor | null;
  onSubmit: (data: {
    name: string;
    contact_name?: string;
    email?: string;
    phone?: string;
    city?: string;
    state?: string;
    is_active?: boolean;
    is_preferred?: boolean;
    notes?: string;
  }) => Promise<boolean>;
}

export function NewLabVendorDialog({ open, onOpenChange, initial, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [active, setActive] = useState(true);
  const [preferred, setPreferred] = useState(false);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (initial) {
        setName(initial.name ?? '');
        setContact(initial.contact_name ?? '');
        setEmail(initial.email ?? '');
        setPhone(initial.phone ?? '');
        setCity(initial.city ?? '');
        setState(initial.state ?? '');
        setActive(initial.is_active ?? true);
        setPreferred(initial.is_preferred ?? false);
        setNotes(initial.notes ?? '');
      } else {
        setName(''); setContact(''); setEmail(''); setPhone('');
        setCity(''); setState(''); setActive(true); setPreferred(false); setNotes('');
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
        contact_name: contact.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        city: city.trim() || undefined,
        state: state.trim() || undefined,
        is_active: active,
        is_preferred: preferred,
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
          <DialogTitle>{initial ? 'Edit Lab Vendor' : 'Add Lab Vendor'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label>Lab Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. ABC Dental Lab" />
          </div>
          <div className="grid grid-cols-2 gap-4">
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
            <div className="space-y-1">
              <Label>City</Label>
              <Input value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>State</Label>
              <Input value={state} onChange={(e) => setState(e.target.value)} placeholder="e.g. CA" />
            </div>
          </div>
          <div className="flex gap-6">
            <label className="flex items-center gap-2">
              <Checkbox checked={active} onCheckedChange={(v) => setActive(!!v)} />
              <span className="text-sm">Active</span>
            </label>
            <label className="flex items-center gap-2">
              <Checkbox checked={preferred} onCheckedChange={(v) => setPreferred(!!v)} />
              <span className="text-sm">Preferred</span>
            </label>
          </div>
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting || !name.trim()}>
              {isSubmitting ? 'Saving…' : (initial ? 'Save Changes' : 'Add Lab')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
