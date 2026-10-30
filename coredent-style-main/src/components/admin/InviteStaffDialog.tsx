// ============================================
// CoreDent PMS - Invite Staff Dialog
// Sends a staff invitation via the staff API
// ============================================

import { useState, useEffect } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, ShieldCheck } from 'lucide-react';
import { staffApi } from '@/services/staffApi';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import type { StaffInvitation, InviteStaffRequest } from '@/types/staff';
import type { UserRole } from '@/types/api';

interface InviteStaffDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (invitation: StaffInvitation) => void;
}

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'dentist', label: 'Dentist (Clinical)' },
  { value: 'hygienist', label: 'Hygienist (Preventive)' },
  { value: 'front_desk', label: 'Front Desk (Admin/Scheduling)' },
  { value: 'admin', label: 'Office Administrator' },
  { value: 'owner', label: 'Practice Owner (Full Access)' },
];

/**
 * Roles the current user is allowed to grant. Only an existing owner may
 * invite another owner — offering it to admins is the UI half of a tenant
 * takeover (paired with backend H1).
 */
const invitableRoles = (currentUserRole?: UserRole | null): { value: UserRole; label: string }[] => {
  if (currentUserRole === 'owner') return ROLE_OPTIONS;
  return ROLE_OPTIONS.filter((option) => option.value !== 'owner');
};

export function InviteStaffDialog({ open, onOpenChange, onSuccess }: InviteStaffDialogProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const availableRoles = invitableRoles(user?.role);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('front_desk');

  // Reset the form whenever the dialog is opened
  useEffect(() => {
    if (open) {
      setFirstName('');
      setLastName('');
      setEmail('');
      setRole('front_desk');
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Defense in depth: never send an owner invite unless the current user is
    // the owner, even if the option somehow got selected.
    if (role === 'owner' && user?.role !== 'owner') {
      toast({
        title: 'Error',
        description: 'Only the practice owner can grant the owner role.',
        variant: 'destructive',
      });
      return;
    }
    setIsSubmitting(true);
    try {
      const payload: InviteStaffRequest = { email, firstName, lastName, role };
      const response = await staffApi.invite(payload);
      if (response.success && response.data) {
        toast({
          title: 'Invitation sent',
          description: `Staff invitation sent to ${email}`,
        });
        onSuccess?.(response.data);
        onOpenChange(false);
      } else {
        toast({
          title: 'Error',
          description: response.error?.message || 'Failed to send invitation',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to send invitation',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px] rounded-3xl p-8">
        <DialogHeader>
          <DialogTitle className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-500" /> Invite Team Member
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400 font-medium mt-0.5">
            Send an email invitation to grant access to CoreDent.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="invite-firstName" className="text-xs font-black uppercase tracking-widest text-slate-400">
                First Name
              </Label>
              <Input
                id="invite-firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="e.g. John"
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-lastName" className="text-xs font-black uppercase tracking-widest text-slate-400">
                Last Name
              </Label>
              <Input
                id="invite-lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="e.g. Doe"
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="invite-email" className="text-xs font-black uppercase tracking-widest text-slate-400">
              Email Address
            </Label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@practice.com"
              className="h-12 rounded-xl border-slate-200 font-medium"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="invite-role" className="text-xs font-black uppercase tracking-widest text-slate-400">
              System Role
            </Label>
            <Select value={role} onValueChange={(val) => setRole(val as UserRole)}>
              <SelectTrigger id="invite-role" className="h-12 rounded-xl border-slate-200 font-bold">
                <SelectValue placeholder="Select system role" />
              </SelectTrigger>
              <SelectContent>
                {availableRoles.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="rounded-xl font-bold h-12 border-slate-200"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12 flex items-center justify-center gap-2"
            >
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send Invitation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
