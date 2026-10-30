import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { clinicApi } from '@/services/clinicApi';
import type { WorkingHours } from '@/types/clinic';
import { Loader2, Save } from 'lucide-react';

interface WorkingHoursTabProps {
  workingHours: WorkingHours;
  onUpdate: (workingHours: WorkingHours) => void;
}

const DAYS_OF_WEEK: { key: keyof WorkingHours; label: string }[] = [
  { key: 'monday', label: 'Monday' },
  { key: 'tuesday', label: 'Tuesday' },
  { key: 'wednesday', label: 'Wednesday' },
  { key: 'thursday', label: 'Thursday' },
  { key: 'friday', label: 'Friday' },
  { key: 'saturday', label: 'Saturday' },
  { key: 'sunday', label: 'Sunday' },
];

export function WorkingHoursTab({ workingHours, onUpdate }: WorkingHoursTabProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [hoursState, setHoursState] = useState<WorkingHours>({ ...workingHours });

  const handleToggleOpen = (day: keyof WorkingHours, checked: boolean) => {
    setHoursState((prev) => ({
      ...prev,
      [day]: {
        ...prev[day],
        isOpen: checked,
      },
    }));
  };

  const handleTimeChange = (day: keyof WorkingHours, field: 'openTime' | 'closeTime', value: string) => {
    setHoursState((prev) => ({
      ...prev,
      [day]: {
        ...prev[day],
        [field]: value,
      },
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const res = await clinicApi.updateSettings({ workingHours: hoursState });
      if (res.success) {
        onUpdate(hoursState);
        toast({
          title: 'Hours Updated',
          description: 'Working hours have been updated successfully.',
        });
      } else {
        toast({
          title: 'Error',
          description: res.error?.message || 'Failed to update working hours',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update working hours due to a network issue.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
      <CardHeader>
        <CardTitle className="text-xl font-black text-slate-800 tracking-tight">Working Hours</CardTitle>
        <CardDescription className="text-slate-400 font-medium">Configure operating hours and days for your practice.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4 divide-y divide-slate-100">
          {DAYS_OF_WEEK.map(({ key, label }) => {
            const daySchedule = hoursState[key] || { isOpen: false, openTime: '09:00', closeTime: '17:00' };
            return (
              <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4 first:pt-0">
                <div className="flex items-center gap-3">
                  <Switch
                    checked={daySchedule.isOpen}
                    onCheckedChange={(checked) => handleToggleOpen(key, checked)}
                  />
                  <div>
                    <span className="font-bold text-slate-700 text-sm block">{label}</span>
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                      {daySchedule.isOpen ? 'Open' : 'Closed'}
                    </span>
                  </div>
                </div>

                {daySchedule.isOpen && (
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <Label className="text-xs font-bold text-slate-400">Open</Label>
                      <Input
                        type="time"
                        value={daySchedule.openTime}
                        onChange={(e) => handleTimeChange(key, 'openTime', e.target.value)}
                        className="h-10 rounded-lg w-28 text-center font-bold"
                      />
                    </div>
                    <span className="text-slate-300 font-medium">—</span>
                    <div className="flex items-center gap-2">
                      <Label className="text-xs font-bold text-slate-400">Close</Label>
                      <Input
                        type="time"
                        value={daySchedule.closeTime}
                        onChange={(e) => handleTimeChange(key, 'closeTime', e.target.value)}
                        className="h-10 rounded-lg w-28 text-center font-bold"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex justify-end pt-4 border-t border-slate-100">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="px-8 h-12 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-black flex items-center justify-center gap-2 shadow-lg shadow-blue-100"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" /> Saving...
              </>
            ) : (
              <>
                <Save className="w-5 h-5" /> Save Hours
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
