import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Camera, Cpu, ImageIcon, Upload } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { patientApi } from '@/services/patientApi';
import { imagingApi } from '@/services/imagingApi';
import type { ImageType } from '@/types/imaging';
import { TwainCaptureDialog } from '@/components/imaging/TwainCaptureDialog';

export default function ImagingHub() {
  const queryClient = useQueryClient();
  const [patientId, setPatientId] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [imageType, setImageType] = useState<ImageType>('xray');
  const [isTwainOpen, setIsTwainOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const patientsQuery = useQuery({ queryKey: ['imaging-patient-picker'], queryFn: () => patientApi.getPatients({ status: 'active', limit: 100 }) });
  const patients = patientsQuery.data?.data ?? [];
  useEffect(() => {
    const firstPatient = patientsQuery.data?.data[0];
    if (!patientId && firstPatient) setPatientId(firstPatient.id);
  }, [patientId, patientsQuery.data]);
  const imagesQuery = useQuery({ queryKey: ['patient-images', patientId], queryFn: () => imagingApi.getImages({ patientId }), enabled: Boolean(patientId) });
  const selectedPatient = patients.find((patient) => patient.id === patientId);

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      imagingApi.uploadImage({ patientId, file, imageType, title: file.name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-images', patientId] });
      setPendingFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-10">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <ImageIcon className="h-8 w-8 text-purple-600" />
            <h1 className="text-3xl font-black text-slate-900">Imaging Library</h1>
          </div>
          <p className="mt-2 text-sm text-slate-500">Live patient images stored through the imaging API & DICOM Part 10 sensor bridge.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => setIsTwainOpen(true)}
            className="bg-purple-600 hover:bg-purple-700 text-white shadow-sm"
            disabled={!patientId}
          >
            <Camera className="mr-2 h-4 w-4" />
            Direct Sensor / TWAIN Capture
          </Button>
        </div>
      </div>
      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><CardTitle>Patient</CardTitle></CardHeader><CardContent><select aria-label="Select patient" className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm md:max-w-lg" value={patientId} onChange={(event) => setPatientId(event.target.value)} disabled={patientsQuery.isLoading || patients.length === 0}><option value="">Select a patient</option>{patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.firstName} {patient.lastName}</option>)}</select>{patientsQuery.isError && <p className="mt-3 text-sm text-red-600">Unable to load patients.</p>}{!patientsQuery.isLoading && patients.length === 0 && <p className="mt-3 text-sm text-slate-500">No active patients found.</p>}</CardContent></Card>

      {selectedPatient && (
        <Card className="rounded-2xl border-slate-200 shadow-sm">
          <CardHeader><CardTitle>Upload image or DICOM File</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.dcm"
                className="hidden"
                onChange={(event) => setPendingFile(event.target.files?.[0] ?? null)}
              />
              <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={!patientId}>
                <Upload className="mr-2 h-4 w-4" />
                Choose file
              </Button>
              <select aria-label="Image type" className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm" value={imageType} onChange={(event) => setImageType(event.target.value as ImageType)}>
                <option value="xray">X-ray</option>
                <option value="photo">Photo</option>
                <option value="scan">Scan</option>
                <option value="document">Document</option>
                <option value="other">Other</option>
              </select>
              <Button
                onClick={() => pendingFile && uploadMutation.mutate(pendingFile)}
                disabled={!pendingFile || uploadMutation.isPending}
              >
                {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
              </Button>
              <Button
                variant="outline"
                className="border-purple-200 text-purple-700 hover:bg-purple-50"
                onClick={() => setIsTwainOpen(true)}
              >
                <Camera className="mr-2 h-4 w-4" />
                Capture from Sensor
              </Button>
            </div>
            {pendingFile && <p className="text-sm text-slate-500">Selected: {pendingFile.name}</p>}
            {uploadMutation.isError && (
              <p className="text-sm text-red-600">
                Upload failed: {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Unknown error'}
              </p>
            )}
            {uploadMutation.isSuccess && <p className="text-sm text-green-700">Image uploaded.</p>}
          </CardContent>
        </Card>
      )}

      <Card className="border-purple-200 bg-purple-50/60">
        <CardContent className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 text-purple-950">
          <div className="flex items-start sm:items-center gap-3">
            <Cpu className="h-6 w-6 text-purple-600 flex-shrink-0 mt-1 sm:mt-0" />
            <div>
              <p className="text-sm font-semibold">Sensor Workstation Bridge & DICOM Engine Active</p>
              <p className="text-xs text-purple-700">Direct streaming enabled for Dexis, Schick 33, Carestream RVG, Vatech EzSensor, Planmeca & TWAIN-compliant devices with native DICOM Part 10 metadata tagging.</p>
            </div>
          </div>
          <Button
            size="sm"
            className="bg-purple-600 hover:bg-purple-700 text-white flex-shrink-0"
            onClick={() => setIsTwainOpen(true)}
            disabled={!patientId}
          >
            <Camera className="mr-1.5 h-3.5 w-3.5" /> Launch Bridge
          </Button>
        </CardContent>
      </Card>

      {selectedPatient && <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><CardTitle>{selectedPatient.firstName} {selectedPatient.lastName} — Images</CardTitle></CardHeader><CardContent>{imagesQuery.isLoading && <p className="text-sm text-slate-500">Loading images…</p>}{imagesQuery.isError && <p className="text-sm text-red-600">Unable to load images for this patient.</p>}{!imagesQuery.isLoading && !imagesQuery.isError && imagesQuery.data?.length === 0 && <p className="text-sm text-slate-500">No images uploaded for this patient.</p>}{imagesQuery.data && imagesQuery.data.length > 0 && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{imagesQuery.data.map((image) => <a key={image.id} href={image.fileUrl} target="_blank" rel="noreferrer" className="group overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="flex aspect-video items-center justify-center bg-slate-100 text-slate-400">{image.fileUrl ? <img src={image.fileUrl} alt={image.title} className="h-full w-full object-cover" /> : <ImageIcon className="h-8 w-8" />}</div><div className="flex items-center justify-between gap-3 p-4"><div><p className="font-bold text-slate-800 group-hover:text-purple-600">{image.title}</p><p className="text-xs text-slate-500">{image.category} · {image.captureDate ? new Date(image.captureDate).toLocaleDateString() : 'Undated'}</p></div></div></a>)}</div>}</CardContent></Card>}

      <TwainCaptureDialog
        open={isTwainOpen}
        onOpenChange={setIsTwainOpen}
        patientId={patientId}
        patientName={selectedPatient ? `${selectedPatient.firstName} ${selectedPatient.lastName}` : ''}
        onCaptured={() => queryClient.invalidateQueries({ queryKey: ['patient-images', patientId] })}
      />
    </div>
  );
}
