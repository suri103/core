import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { staffApi } from '@/services/staffApi';
import type { StaffMember, StaffInvitation } from '@/types/staff';
import { Loader2, Plus, Mail, ToggleLeft, ToggleRight, ShieldCheck, MailCheck } from 'lucide-react';

export function StaffSettingsTab() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [invitations, setInvitations] = useState<StaffInvitation[]>([]);
  const [isInviteOpen, setIsInviteOpen] = useState(false);

  // Invite form state
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'owner' | 'admin' | 'dentist' | 'hygienist' | 'front_desk'>('front_desk');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  const loadStaffData = async () => {
    setLoading(true);
    try {
      const [staffRes, inviteRes] = await Promise.all([
        staffApi.list(),
        staffApi.listInvitations(),
      ]);
      if (staffRes.success && staffRes.data) {
        // Handle pagination response vs array
        const list = Array.isArray(staffRes.data) ? staffRes.data : (staffRes.data as any).data || [];
        setStaff(list);
      }
      if (inviteRes.success && inviteRes.data) {
        setInvitations(inviteRes.data);
      }
    } catch (err) {
      console.error('Failed to load staff data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStaffData();
  }, []);

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const res = await staffApi.invite({ email, role, firstName, lastName });
      if (res.success && res.data) {
        setInvitations((prev) => [...prev, res.data!]);
        toast({
          title: 'Invitation Sent',
          description: `Staff invitation sent to ${email}`,
        });
        setIsInviteOpen(false);
        // Clear
        setEmail('');
        setFirstName('');
        setLastName('');
      } else {
        toast({
          title: 'Error',
          description: res.error?.message || 'Failed to send invitation',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to send invitation.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleStatus = async (member: StaffMember) => {
    const isCurrentlyActive = member.status === 'active';
    try {
      const res = isCurrentlyActive 
        ? await staffApi.deactivate(member.id)
        : await staffApi.reactivate(member.id);
      
      if (res.success && res.data) {
        setStaff((prev) => prev.map((s) => (s.id === member.id ? res.data! : s)));
        toast({
          title: 'Status Updated',
          description: `${member.firstName} ${member.lastName} has been ${isCurrentlyActive ? 'deactivated' : 'reactivated'}.`,
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update member status.',
        variant: 'destructive',
      });
    }
  };

  const handleCancelInvitation = async (id: string) => {
    try {
      const res = await staffApi.cancelInvitation(id);
      if (res.success) {
        setInvitations((prev) => prev.filter((i) => i.id !== id));
        toast({
          title: 'Invitation Canceled',
          description: 'The invitation has been canceled.',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to cancel invitation.',
        variant: 'destructive',
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
        <CardHeader className="flex flex-row justify-between items-center pb-4">
          <div>
            <CardTitle className="text-xl font-black text-slate-800 tracking-tight">Active Team Members</CardTitle>
            <CardDescription className="text-slate-400 font-medium">Manage clinical staff, dentists, hygienists, and front desk office accounts.</CardDescription>
          </div>
          <Button onClick={() => setIsInviteOpen(true)} className="h-10 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 shadow-md shadow-blue-100">
            <Plus className="w-4 h-4" /> Invite Member
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {staff.map((member) => (
              <div key={member.id} className="flex items-center justify-between p-4 border border-slate-100 rounded-2xl bg-white hover:border-slate-200 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-lg">
                    {member.firstName[0]}{member.lastName[0]}
                  </div>
                  <div>
                    <p className="font-black text-slate-800 text-sm">{member.firstName} {member.lastName}</p>
                    <p className="text-xs text-slate-400 font-bold flex items-center gap-1">
                      <Mail className="w-3 h-3" /> {member.email}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <Badge variant="outline" className="font-bold uppercase tracking-wider text-[9px] bg-slate-50 text-slate-500 border-none capitalize px-3 py-1">
                    {member.role.replace('_', ' ')}
                  </Badge>
                  <Button
                    variant="ghost"
                    onClick={() => handleToggleStatus(member)}
                    className={`h-9 px-3 rounded-lg font-bold text-xs flex items-center gap-1.5 ${
                      member.status === 'active' 
                        ? 'text-emerald-600 hover:bg-emerald-50' 
                        : 'text-slate-400 hover:bg-slate-50'
                    }`}
                  >
                    {member.status === 'active' ? (
                      <>
                        <ToggleRight className="w-5 h-5 text-emerald-500" /> Active
                      </>
                    ) : (
                      <>
                        <ToggleLeft className="w-5 h-5 text-slate-300" /> Suspended
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      {invitations.length > 0 && (
        <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
          <CardHeader>
            <CardTitle className="text-lg font-black text-slate-800 tracking-tight">Pending Invitations</CardTitle>
            <CardDescription className="text-slate-400 font-medium">Invitations sent to team members waiting to register.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {invitations.map((invite) => (
              <div key={invite.id} className="flex items-center justify-between p-4 border border-slate-100 rounded-2xl bg-white">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-500 flex items-center justify-center">
                    <MailCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-700 text-xs">{invite.firstName} {invite.lastName}</p>
                    <p className="text-[11px] text-slate-400 font-medium">{invite.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Badge variant="outline" className="font-bold uppercase tracking-wider text-[8px] bg-purple-50 text-purple-600 border-none capitalize">
                    {invite.role.replace('_', ' ')}
                  </Badge>
                  <Button
                    variant="ghost"
                    onClick={() => handleCancelInvitation(invite.id)}
                    className="h-8 px-2.5 rounded-lg text-[10px] font-bold text-red-500 hover:bg-red-50"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Invite Member Dialog */}
      <Dialog open={isInviteOpen} onOpenChange={setIsInviteOpen}>
        <DialogContent className="sm:max-w-[420px] rounded-3xl p-8">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-blue-500" /> Invite Team Member
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400 font-medium mt-0.5">
              Send an email invitation to grant access to CoreDent.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleInviteSubmit} className="space-y-4 py-3">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first-name" className="text-xs font-black uppercase tracking-widest text-slate-400">First Name</Label>
                <Input
                  id="first-name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="e.g. John"
                  className="h-12 rounded-xl border-slate-200 font-bold"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last-name" className="text-xs font-black uppercase tracking-widest text-slate-400">Last Name</Label>
                <Input
                  id="last-name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="e.g. Doe"
                  className="h-12 rounded-xl border-slate-200 font-bold"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="invite-email" className="text-xs font-black uppercase tracking-widest text-slate-400">Email Address</Label>
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
              <Label htmlFor="invite-role" className="text-xs font-black uppercase tracking-widest text-slate-400">System Role</Label>
              <Select value={role} onValueChange={(val: any) => setRole(val)}>
                <SelectTrigger id="invite-role" className="h-12 rounded-xl border-slate-200 font-bold">
                  <SelectValue placeholder="Select system role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dentist">Dentist (Clinical)</SelectItem>
                  <SelectItem value="hygienist">Hygienist (Preventive)</SelectItem>
                  <SelectItem value="front_desk">Front Desk (Admin/Scheduling)</SelectItem>
                  <SelectItem value="admin">Office Administrator</SelectItem>
                  <SelectItem value="owner">Practice Owner (Full Access)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4">
              <Button type="button" variant="outline" onClick={() => setIsInviteOpen(false)} className="rounded-xl font-bold h-12 border-slate-200">
                Cancel
              </Button>
              <Button type="submit" disabled={isSaving} className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12 flex items-center justify-center gap-2">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send Invitation'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
