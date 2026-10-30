import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { patientApi } from '@/services/patientApi';
import { StickyNote, AlertTriangle } from 'lucide-react';
import type { PatientNote } from '@/types/patient';

interface AddNoteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patientId: string;
  onSave: () => void;
}

export function AddNoteDialog({
  open,
  onOpenChange,
  patientId,
  onSave,
}: AddNoteDialogProps) {
  const { toast } = useToast();
  const { user } = useAuth();

  const [content, setContent] = useState('');
  const [type, setType] = useState<PatientNote['type']>('general');
  const [isAlert, setIsAlert] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setIsSubmitting(true);
    try {
      const authorId = user?.id || 'staff';
      const authorName = user ? `${user.firstName} ${user.lastName}` : 'Staff Member';

      await patientApi.addNote(patientId, {
        type,
        content: content.trim(),
        createdBy: authorId,
        createdByName: authorName,
        isAlert: type === 'alert' ? true : isAlert,
        isPinned,
      });

      toast({
        title: 'Note Recorded',
        description: 'Note has been successfully added to patient timeline.',
      });

      setContent('');
      setType('general');
      setIsAlert(false);
      setIsPinned(false);
      onSave();
      onOpenChange(false);
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to record patient note.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-card/95 border border-border backdrop-blur-md text-foreground">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2">
            <StickyNote className="h-5 w-5 text-primary" />
            Add Patient Note
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleFormSubmit} className="space-y-4 pt-2">
          {/* Note Type */}
          <div className="space-y-2">
            <Label htmlFor="noteType">Note Category</Label>
            <Select 
              value={type} 
              onValueChange={(val) => {
                setType(val as PatientNote['type']);
                if (val === 'alert') {
                  setIsAlert(true);
                }
              }}
            >
              <SelectTrigger id="noteType" className="bg-background/60 border-border">
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent className="bg-card border-border">
                <SelectItem value="general" className="cursor-pointer">General Memo</SelectItem>
                <SelectItem value="clinical" className="cursor-pointer">Clinical Details</SelectItem>
                <SelectItem value="billing" className="cursor-pointer">Billing/Ledger Memo</SelectItem>
                <SelectItem value="communication" className="cursor-pointer font-normal text-muted-foreground">Communication Log</SelectItem>
                <SelectItem value="alert" className="cursor-pointer text-rose-500 font-semibold focus:text-rose-500">
                  <span className="flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" /> Medical Alert Flag
                  </span>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Note Text */}
          <div className="space-y-2">
            <Label htmlFor="noteContent">Note Content</Label>
            <Textarea
              id="noteContent"
              placeholder="Type clinical summary, special precautions, patient request or memo details here..."
              value={content}
              onChange={e => setContent(e.target.value)}
              className="h-32 bg-background/60 border-border resize-none"
              required
            />
          </div>

          {/* Flags */}
          <div className="rounded-xl border border-border bg-accent/10 p-4 space-y-4 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="alertFlag" className="font-semibold block cursor-pointer">Critical Alert Flag</Label>
                <span className="text-[10px] text-muted-foreground">Visually flags patient profile with medical hazard warning</span>
              </div>
              <Switch 
                id="alertFlag" 
                checked={isAlert} 
                onCheckedChange={setIsAlert}
                disabled={type === 'alert'}
              />
            </div>

            <div className="flex items-center justify-between border-t border-border/40 pt-4">
              <div>
                <Label htmlFor="pinFlag" className="font-semibold block cursor-pointer">Pin to Profile</Label>
                <span className="text-[10px] text-muted-foreground">Keeps note visible at top of patient dashboard</span>
              </div>
              <Switch 
                id="pinFlag" 
                checked={isPinned} 
                onCheckedChange={setIsPinned}
              />
            </div>
          </div>

          <DialogFooter className="pt-2 border-t border-border/50">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="border-border bg-background hover:bg-accent text-foreground"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !content.trim()}
              className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-6"
            >
              {isSubmitting ? 'Saving...' : 'Save Note'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
