import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
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
import type { Chair } from '@/types/clinic';
import { Loader2, Plus, Pencil, Trash2, ShieldAlert } from 'lucide-react';

interface ChairsTabProps {
  chairs: Chair[];
  onUpdate: (chairs: Chair[]) => void;
}

export function ChairsTab({ chairs, onUpdate }: ChairsTabProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingChair, setEditingChair] = useState<Chair | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [color, setColor] = useState('#3B82F6');

  const openAddDialog = () => {
    setEditingChair(null);
    setName('');
    setDescription('');
    setIsActive(true);
    setColor('#3B82F6');
    setIsDialogOpen(true);
  };

  const openEditDialog = (chair: Chair) => {
    setEditingChair(chair);
    setName(chair.name);
    setDescription(chair.description || '');
    setIsActive(chair.isActive);
    setColor(chair.color || '#3B82F6');
    setIsDialogOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (editingChair) {
        // Edit chair
        const res = await clinicApi.updateChair(editingChair.id, { name, description, isActive, color });
        if (res.success && res.data) {
          onUpdate(chairs.map((c) => (c.id === editingChair.id ? res.data! : c)));
          toast({
            title: 'Chair Updated',
            description: `Operatory "${name}" updated successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: 'Error',
            description: res.error?.message || 'Failed to update chair',
            variant: 'destructive',
          });
        }
      } else {
        // Create chair
        const res = await clinicApi.createChair({ name, description, isActive, color });
        if (res.success && res.data) {
          onUpdate([...chairs, res.data]);
          toast({
            title: 'Chair Created',
            description: `Operatory "${name}" created successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: 'Error',
            description: res.error?.message || 'Failed to create chair',
            variant: 'destructive',
          });
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to save chair due to a network error.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await clinicApi.deleteChair(id);
      if (res.success) {
        onUpdate(chairs.filter((c) => c.id !== id));
        toast({
          title: 'Chair Deleted',
          description: 'Operatory deleted successfully.',
        });
      } else {
        toast({
          title: 'Error',
          description: res.error?.message || 'Failed to delete chair',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete chair.',
        variant: 'destructive',
      });
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
      <CardHeader className="flex flex-row justify-between items-center pb-4">
        <div>
          <CardTitle className="text-xl font-black text-slate-800 tracking-tight">Operatory Chairs</CardTitle>
          <CardDescription className="text-slate-400 font-medium">Add or configure chairs and treatment operatories.</CardDescription>
        </div>
        <Button onClick={openAddDialog} className="h-10 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 shadow-md shadow-blue-100">
          <Plus className="w-4 h-4" /> Add Operatory
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {chairs.length === 0 ? (
          <div className="text-center py-12 text-slate-400 space-y-3 bg-slate-50/50 rounded-2xl border border-dashed border-slate-100">
            <ShieldAlert className="w-8 h-8 mx-auto text-slate-300" />
            <p className="font-bold text-sm">No chairs configured</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {chairs.map((chair) => (
              <div key={chair.id} className="p-5 border border-slate-100 rounded-2xl flex flex-col justify-between gap-4 bg-white hover:border-blue-200 transition-colors">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="font-black text-slate-800 text-base">{chair.name}</h4>
                    <Badge variant={chair.isActive ? 'default' : 'secondary'} className={chair.isActive ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-50/80 border-none font-bold' : ''}>
                      {chair.isActive ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  {chair.description && <p className="text-xs text-slate-400 font-medium">{chair.description}</p>}
                </div>

                <div className="flex justify-between items-center pt-3 border-t border-slate-50">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: chair.color || '#3B82F6' }} />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Color Code</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button variant="ghost" size="icon" onClick={() => openEditDialog(chair)} className="h-8 w-8 rounded-lg text-slate-500">
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
                          <AlertDialogTitle>Delete Operatory?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This will permanently delete "{chair.name}". All scheduled appointments tied to this chair will lose their operatory assignment.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(chair.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Chair Dialog */}
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="sm:max-w-[420px] rounded-3xl p-8">
            <DialogHeader>
              <DialogTitle className="text-xl font-black text-slate-800 tracking-tight">
                {editingChair ? 'Edit Operatory' : 'Add New Operatory'}
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-400 font-medium mt-0.5">
                Setup operatory chairs to manage scheduling slots.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleFormSubmit} className="space-y-5 py-3">
              <div className="space-y-2">
                <Label htmlFor="chair-name" className="text-xs font-black uppercase tracking-widest text-slate-400">Chair/Operatory Name</Label>
                <Input
                  id="chair-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Chair 1 or Operatory A"
                  className="h-12 rounded-xl border-slate-200 font-bold"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="chair-desc" className="text-xs font-black uppercase tracking-widest text-slate-400">Description (Optional)</Label>
                <Input
                  id="chair-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Pediatric & general hygiene"
                  className="h-12 rounded-xl border-slate-200 font-medium"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="chair-color" className="text-xs font-black uppercase tracking-widest text-slate-400">Calendar Color</Label>
                  <div className="flex gap-2 items-center">
                    <Input
                      id="chair-color"
                      type="color"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      className="w-12 h-12 p-0 border border-slate-200 rounded-xl cursor-pointer"
                    />
                    <span className="text-xs font-bold text-slate-500 uppercase">{color}</span>
                  </div>
                </div>
                <div className="space-y-2 flex flex-col justify-center">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400 mb-1">Status</Label>
                  <div className="flex items-center gap-2">
                    <Switch checked={isActive} onCheckedChange={setIsActive} />
                    <span className="text-xs font-bold text-slate-600">{isActive ? 'Active' : 'Inactive'}</span>
                  </div>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-4">
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} className="rounded-xl font-bold h-12 border-slate-200">
                  Cancel
                </Button>
                <Button type="submit" disabled={isSaving} className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12">
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : editingChair ? 'Save Changes' : 'Create Chair'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
