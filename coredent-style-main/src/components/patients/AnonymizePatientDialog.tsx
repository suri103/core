import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertTriangle } from 'lucide-react';
import { patientApi } from '@/services/patientApi';
import { useToast } from '@/hooks/use-toast';
import type { PatientRecord } from '@/types/patient';

interface AnonymizePatientDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patient: PatientRecord | null;
  onAnonymized: () => void;
}

/**
 * GDPR right-to-erasure confirmation. Irreversible: personal data is
 * scrubbed in place (billing history retained, anonymized) so custodial
 * invoices, claims and ledger rows stay intact. Mirrors the one-way
 * semantics of the backend POST /patients/{id}/anonymize endpoint.
 */
export function AnonymizePatientDialog({
  open,
  onOpenChange,
  patient,
  onAnonymized,
}: AnonymizePatientDialogProps) {
  const { toast } = useToast();
  const [confirmName, setConfirmName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setConfirmName('');
      setIsSubmitting(false);
    }
  }, [open ]);

  if (!patient) return null;

  const expected = `${patient.firstName} ${patient.lastName}`.trim();
  const confirmed = confirmName.trim().toLowerCase() === expected.toLowerCase();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!confirmed || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await patientApi.anonymizePatient(patient.id);
      toast({
        title: 'Patient data erased',
        description: 'Personal data has been permanently erased. Billing history retained.',
      });
      onAnonymized();
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to erase patient data. Please try again.',
        variant: 'destructive',
      });
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-card/95 border border-border backdrop-blur-md text-foreground">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Erase Patient Data?
          </DialogTitle>
          <DialogDescription>
            This permanently removes <strong>{expected}</strong>&apos;s personal data
            (name, contact, medical history, portal access) from CoreDent.
            Billing history is retained but anonymized.
            <br /><br />
            <strong>This cannot be undone.</strong> Type the patient&apos;s full name
            to confirm.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="anonymize-confirm">Patient full name</Label>
            <Input
              id="anonymize-confirm"
              value={confirmName}
              onChange={(event) => setConfirmName(event.target.value)}
              placeholder={expected}
              autoComplete="off"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={!confirmed || isSubmitting}>
              {isSubmitting ? 'Erasing...' : 'Erase Permanently'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
