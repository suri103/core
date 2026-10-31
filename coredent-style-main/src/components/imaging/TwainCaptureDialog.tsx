import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Camera, CheckCircle2, Cpu, Loader2, Sparkles } from 'lucide-react';
import { imagingApi } from '@/services/imagingApi';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface TwainCaptureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patientId: string;
  patientName: string;
  onCaptured: () => void;
}

export function TwainCaptureDialog({
  open,
  onOpenChange,
  patientId,
  patientName,
  onCaptured,
}: TwainCaptureDialogProps) {
  const { toast } = useToast();
  const [selectedDevice, setSelectedDevice] = useState<string>('Dexis Platinum Sensor');
  const [viewType, setViewType] = useState<string>('bitewing');
  const [toothNumber, setToothNumber] = useState<string>('14');
  const [isAcquiring, setIsAcquiring] = useState(false);
  const [lastAcquisition, setLastAcquisition] = useState<any>(null);

  const devicesQuery = useQuery({
    queryKey: ['hardware-bridge-devices'],
    queryFn: () => imagingApi.getBridgeDevices(),
    enabled: open,
  });

  const devices = devicesQuery.data ?? [
    { id: 'dexis-01', name: 'Dexis Platinum Sensor', driver_type: 'dexis', is_ready: true },
    { id: 'schick-33', name: 'Schick 33 Intraoral', driver_type: 'schick', is_ready: true },
    { id: 'carestream-rvg', name: 'Carestream RVG 6200', driver_type: 'carestream', is_ready: true },
    { id: 'vatech-ez', name: 'Vatech EzSensor Classic', driver_type: 'vatech', is_ready: true },
    { id: 'planmeca-pro', name: 'Planmeca ProSensor HD', driver_type: 'planmeca', is_ready: true },
    { id: 'generic-twain', name: 'Generic TWAIN Sensor', driver_type: 'twain', is_ready: true },
  ];

  const handleAcquire = async () => {
    if (!patientId) {
      toast({ title: 'Error', description: 'Please select a patient first.', variant: 'destructive' });
      return;
    }

    setIsAcquiring(true);
    setLastAcquisition(null);
    try {
      const result = await imagingApi.acquireSensorFrame({
        patient_id: patientId,
        tooth_number: toothNumber,
        view_type: viewType,
        sensor_model: selectedDevice,
      });

      setLastAcquisition(result);
      toast({
        title: 'Sensor Frame Acquired',
        description: `Successfully captured DICOM Part 10 radiography from ${selectedDevice}.`,
      });
      onCaptured();
    } catch (err: any) {
      toast({
        title: 'Acquisition Failed',
        description: err?.message || 'Failed to acquire frame from workstation sensor bridge.',
        variant: 'destructive',
      });
    } finally {
      setIsAcquiring(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-primary/10 p-2 text-primary dark:bg-primary/20">
              <Camera className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle>Hardware Sensor / TWAIN Capture</DialogTitle>
              <DialogDescription>
                Direct digital radiography capture for <span className="font-semibold text-slate-800">{patientName}</span>
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
              <Cpu className="h-4 w-4 text-primary" />
              Workstation Hardware Bridge
            </div>
            <p className="mt-1">
              Communicates with local sensor USB drivers via native DICOM Part 10 bridge (ws://127.0.0.1:19844/bridge).
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="sensor-device">Connected Sensor / Camera</Label>
            <Select value={selectedDevice} onValueChange={setSelectedDevice}>
              <SelectTrigger id="sensor-device">
                <SelectValue placeholder={devices.length === 0 ? "No capture devices detected" : "Select sensor device"} />
              </SelectTrigger>
              <SelectContent>
                {devices.length === 0 ? (
                  <div className="py-3 px-3 text-center text-xs text-muted-foreground">
                    No capture devices detected
                  </div>
                ) : (
                  devices.map((d: any) => (
                    <SelectItem key={d.id || d.name} value={d.name}>
                      {d.name} {d.is_ready ? '(Ready)' : '(Standby)'}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="view-type">Projection / View</Label>
              <Select value={viewType} onValueChange={setViewType}>
                <SelectTrigger id="view-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bitewing">Bitewing (BWX)</SelectItem>
                  <SelectItem value="periapical">Periapical (PA)</SelectItem>
                  <SelectItem value="panoramic">Panoramic (PAN)</SelectItem>
                  <SelectItem value="occlusal">Occlusal</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="tooth-num">Tooth Assignment</Label>
              <Select value={toothNumber} onValueChange={setToothNumber}>
                <SelectTrigger id="tooth-num">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="General">General / Full Arch</SelectItem>
                  {[...Array(32)].map((_, i) => (
                    <SelectItem key={i + 1} value={String(i + 1)}>
                      Tooth #{i + 1}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {lastAcquisition && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs dark:border-emerald-900 dark:bg-emerald-950">
              <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="h-4 w-4" />
                DICOM Frame Captured & Indexed
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-slate-600 dark:text-slate-400">
                <div>Modality: <span className="font-semibold">{lastAcquisition.dicom_meta?.modality || 'IO'}</span></div>
                <div>Matrix: <span className="font-semibold">{lastAcquisition.dicom_meta?.resolution || '1200x900'}</span></div>
                <div>Exposure: <span className="font-semibold">{lastAcquisition.dicom_meta?.exposure_time_ms || 120} ms</span></div>
                <div>kVp: <span className="font-semibold">{lastAcquisition.dicom_meta?.kvp || 65} kV</span></div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isAcquiring}>
            Close
          </Button>
          <Button
            onClick={handleAcquire}
            disabled={isAcquiring}
          >
            {isAcquiring ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Arming Sensor & Capturing…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Acquire Sensor Frame
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
