// ============================================
// CoreDent PMS - Edit Staff Dialog
// Updates an existing staff member's details and role
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
import { Loader2, Shield } from 'lucide-react';
import { staffApi } from '@/services/staffApi';
import { useToast } from '@/hooks/use-toast';
import type { StaffMember, UpdateStaffRequest } from '@/types/staff';
import type { UserRole } from '@/types/api';

interface EditStaffDialogProps {
  staff: StaffMember | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (updated: StaffMember) => void;
}

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'dentist', label: 'Dentist (Clinical)' },
  { value: 'hygienist', label: 'Hygienist (Preventive)' },
  { value: 'front_desk', label: 'Front Desk (Admin/Scheduling)' },
  { value: 'accountant', label: 'Accountant (Finance & Billing)' },
  { value: 'admin', label: 'Office Administrator' },
  { value: 'owner', label: 'Practice Owner (Full Access)' },
];

export function EditStaffDialog({ staff, open, onOpenChange, onSuccess }: EditStaffDialogProps) {
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('front_desk');

  // Populate the form whenever the target staff member changes
  useEffect(() => {
    if (staff) {
      setFirstName(staff.firstName);
      setLastName(staff.lastName);
      setEmail(staff.email);
      setRole(staff.role);
    }
  }, [staff]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!staff) return;
    setIsSubmitting(true);
    try {
      const payload: UpdateStaffRequest = { firstName, lastName, email, role };
      const response = await staffApi.update(staff.id, payload);
      if (response.success && response.data) {
        toast({
          title: 'Staff updated',
          description: `${firstName} ${lastName} has been updated.`,
        });
        onSuccess?.(response.data);
        onOpenChange(false);
      } else {
        toast({
          title: 'Error',
          description: response.error?.message || 'Failed to update staff member',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to update staff member',
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
            <Shield className="w-5 h-5 text-blue-500" /> Edit Staff Member
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400 font-medium mt-0.5">
            Update name, email, or system role.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="edit-firstName" className="text-xs font-black uppercase tracking-widest text-slate-400">
                First Name
              </Label>
              <Input
                id="edit-firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-lastName" className="text-xs font-black uppercase tracking-widest text-slate-400">
                Last Name
              </Label>
              <Input
                id="edit-lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-email" className="text-xs font-black uppercase tracking-widest text-slate-400">
              Email Address
            </Label>
            <Input
              id="edit-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-12 rounded-xl border-slate-200 font-medium"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-role" className="text-xs font-black uppercase tracking-widest text-slate-400">
              System Role
            </Label>
            <Select value={role} onValueChange={(val) => setRole(val as UserRole)}>
              <SelectTrigger id="edit-role" className="h-12 rounded-xl border-slate-200 font-bold">
                <SelectValue placeholder="Select system role" />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((opt) => (
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
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
