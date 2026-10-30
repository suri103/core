import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { clinicApi } from '@/services/clinicApi';
import type { AppointmentTypeConfig } from '@/types/clinic';
import { Loader2, Plus, Pencil, Trash2, Calendar, ShieldAlert } from 'lucide-react';

interface AppointmentTypesTabProps {
  appointmentTypes: AppointmentTypeConfig[];
  onUpdate: (types: AppointmentTypeConfig[]) => void;
}

export function AppointmentTypesTab({ appointmentTypes, onUpdate }: AppointmentTypesTabProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState<AppointmentTypeConfig | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [duration, setDuration] = useState(30);
  const [color, setColor] = useState('#3B82F6');
  const [isActive, setIsActive] = useState(true);
  const [allowOnlineBooking, setAllowOnlineBooking] = useState(true);
  const [description, setDescription] = useState('');

  const openAddDialog = () => {
    setEditingType(null);
    setName('');
    setCode('');
    setDuration(30);
    setColor('#3B82F6');
    setIsActive(true);
    setAllowOnlineBooking(true);
    setDescription('');
    setIsDialogOpen(true);
  };

  const openEditDialog = (type: AppointmentTypeConfig) => {
    setEditingType(type);
    setName(type.name);
    setCode(type.code || '');
    setDuration(type.duration);
    setColor(type.color || '#3B82F6');
    setIsActive(type.isActive);
    setAllowOnlineBooking(type.allowOnlineBooking);
    setDescription(type.description || '');
    setIsDialogOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        name,
        code,
        duration: Number(duration),
        color,
        isActive,
        allowOnlineBooking,
        description: description.trim() || undefined,
      };

      if (editingType) {
        const res = await clinicApi.updateAppointmentType(editingType.id, payload);
        if (res.success && res.data) {
          onUpdate(appointmentTypes.map((t) => (t.id === editingType.id ? res.data! : t)));
          toast({
            title: 'Type Updated',
            description: `Appointment type "${name}" updated successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: 'Error',
            description: res.error?.message || 'Failed to update appointment type',
            variant: 'destructive',
          });
        }
      } else {
        const res = await clinicApi.createAppointmentType(payload);
        if (res.success && res.data) {
          onUpdate([...appointmentTypes, res.data]);
          toast({
            title: 'Type Created',
            description: `Appointment type "${name}" created successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: 'Error',
            description: res.error?.message || 'Failed to create appointment type',
            variant: 'destructive',
          });
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'An unexpected network error occurred.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await clinicApi.deleteAppointmentType(id);
      if (res.success) {
        onUpdate(appointmentTypes.filter((t) => t.id !== id));
        toast({
          title: 'Type Deleted',
          description: 'Appointment type deleted successfully.',
        });
      } else {
        toast({
          title: 'Error',
          description: res.error?.message || 'Failed to delete type',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete appointment type.',
        variant: 'destructive',
      });
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
      <CardHeader className="flex flex-row justify-between items-center pb-4">
        <div>
          <CardTitle className="text-xl font-black text-slate-800 tracking-tight">Appointment Types</CardTitle>
          <CardDescription className="text-slate-400 font-medium">Manage clinical slots, procedure times, and patient scheduling types.</CardDescription>
        </div>
        <Button onClick={openAddDialog} className="h-10 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 shadow-md shadow-blue-100">
          <Plus className="w-4 h-4" /> Add Type
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {appointmentTypes.length === 0 ? (
          <div className="text-center py-12 text-slate-400 space-y-3 bg-slate-50/50 rounded-2xl border border-dashed border-slate-100">
            <ShieldAlert className="w-8 h-8 mx-auto text-slate-300" />
            <p className="font-bold text-sm">No appointment types configured</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {appointmentTypes.map((type) => (
              <div key={type.id} className="p-5 border border-slate-100 rounded-2xl flex flex-col justify-between gap-4 bg-white hover:border-blue-200 transition-colors">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="font-black text-slate-800 text-base">{type.name}</h4>
                    <div className="flex gap-1.5">
                      {type.code && <Badge variant="secondary" className="font-mono text-[9px] font-bold">{type.code}</Badge>}
                      <Badge variant={type.isActive ? 'default' : 'secondary'} className={type.isActive ? 'bg-emerald-50 text-emerald-600 border-none font-bold' : ''}>
                        {type.isActive ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-xs font-bold text-slate-500 flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-blue-500" /> {type.duration} minutes
                  </p>
                  {type.description && <p className="text-xs text-slate-400 font-medium leading-relaxed">{type.description}</p>}
                </div>

                <div className="flex justify-between items-center pt-3 border-t border-slate-50">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: type.color || '#3B82F6' }} />
                    <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">
                      {type.allowOnlineBooking ? 'Online Booking Enabled' : 'Staff Schedule Only'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button variant="ghost" size="icon" onClick={() => openEditDialog(type)} className="h-8 w-8 rounded-lg text-slate-500">
                      <Pencil className="w-3.5 h-3.5" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg text-red-500 hover:bg-red-50">
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Appointment Type?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{type.name}"? Active appointments currently scheduled under this type will not be canceled but the type option will be removed.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(type.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Type Dialog */}
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="sm:max-w-[420px] rounded-3xl p-8">
            <DialogHeader>
              <DialogTitle className="text-xl font-black text-slate-800 tracking-tight">
                {editingType ? 'Edit Appointment Type' : 'Add Appointment Type'}
              </DialogTitle>
              <DialogDescription className="text-xs font-medium text-slate-400">
                Configure the appointment name, duration, booking visibility, and calendar color.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleFormSubmit} className="space-y-4 py-3">
              <div className="space-y-2">
                <Label htmlFor="type-name" className="text-xs font-black uppercase tracking-widest text-slate-400">Type Name</Label>
                <Input
                  id="type-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Periodic Cleaning"
                  className="h-12 rounded-xl border-slate-200 font-bold"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="type-code" className="text-xs font-black uppercase tracking-widest text-slate-400">CDT Code (Optional)</Label>
                  <Input
                    id="type-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="e.g. D1110"
                    className="h-12 rounded-xl border-slate-200 font-bold uppercase"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="type-duration" className="text-xs font-black uppercase tracking-widest text-slate-400">Duration (Mins)</Label>
                  <Input
                    id="type-duration"
                    type="number"
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="h-12 rounded-xl border-slate-200 font-bold"
                    min={5}
                    step={5}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="type-desc" className="text-xs font-black uppercase tracking-widest text-slate-400">Description (Optional)</Label>
                <Input
                  id="type-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Routine examination and dental scaling"
                  className="h-12 rounded-xl border-slate-200 font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Calendar Color</Label>
                  <div className="flex gap-2 items-center">
                    <Input
                      type="color"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      className="w-12 h-12 p-0 border border-slate-200 rounded-xl cursor-pointer"
                    />
                    <span className="text-xs font-bold text-slate-500 uppercase">{color}</span>
                  </div>
                </div>
                <div className="space-y-3 flex flex-col justify-center">
                  <div className="flex items-center gap-2">
                    <Switch checked={isActive} onCheckedChange={setIsActive} />
                    <Label className="text-xs font-bold text-slate-600">Active</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch checked={allowOnlineBooking} onCheckedChange={setAllowOnlineBooking} />
                    <Label className="text-xs font-bold text-slate-600">Allow Online Booking</Label>
                  </div>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-4">
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} className="rounded-xl font-bold h-12 border-slate-200">
                  Cancel
                </Button>
                <Button type="submit" disabled={isSaving} className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12">
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : editingType ? 'Save Changes' : 'Create Type'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
