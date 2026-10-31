import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Camera, Cpu, ImageIcon, Upload } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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

  const patientsQuery = useQuery({
    queryKey: ['imaging-patient-picker'],
    queryFn: () => patientApi.getPatients({ limit: 100 }),
  });
  const patients = patientsQuery.data?.data ?? [];

  useEffect(() => {
    const firstPatient = patientsQuery.data?.data[0];
    if (!patientId && firstPatient) setPatientId(firstPatient.id);
  }, [patientId, patientsQuery.data]);

  const imagesQuery = useQuery({
    queryKey: ['patient-images', patientId],
    queryFn: () => imagingApi.getImages({ patientId }),
    enabled: Boolean(patientId),
  });
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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Imaging Library</h1>
          <p className="text-muted-foreground mt-1">
            Live patient images stored through the imaging API &amp; DICOM Part 10 sensor bridge.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => setIsTwainOpen(true)}
            disabled={!patientId}
          >
            <Camera className="mr-2 h-4 w-4" />
            Direct Sensor / TWAIN Capture
          </Button>
        </div>
      </div>

      {/* Patient Picker Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">Select Patient</CardTitle>
          <CardDescription>
            Choose a patient record to view or capture dental radiographs and clinical imagery.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-w-md">
            <Select
              value={patientId}
              onValueChange={setPatientId}
              disabled={patientsQuery.isLoading || patients.length === 0}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={
                    patientsQuery.isLoading
                      ? 'Loading patients…'
                      : patients.length === 0
                      ? 'No active patients found'
                      : 'Select a patient'
                  }
                />
              </SelectTrigger>
              <SelectContent className="max-h-60 overflow-y-auto">
                {patientsQuery.isLoading ? (
                  <div className="py-3 px-3 text-center text-xs text-muted-foreground">
                    Loading patients…
                  </div>
                ) : patients.length === 0 ? (
                  <div className="py-3 px-3 text-center text-xs text-muted-foreground">
                    No active patients found in practice
                  </div>
                ) : (
                  patients.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id}>
                      {patient.firstName} {patient.lastName}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          {patientsQuery.isError && (
            <p className="mt-2 text-sm text-destructive">Unable to load patient records.</p>
          )}
        </CardContent>
      </Card>

      {/* Upload File Card */}
      {selectedPatient && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Upload Image or DICOM File</CardTitle>
            <CardDescription>
              Assign new radiographs, intraoral scans, or photographs to {selectedPatient.firstName} {selectedPatient.lastName}.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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

              <div className="w-[140px]">
                <Select value={imageType} onValueChange={(val) => setImageType(val as ImageType)}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="xray">X-ray</SelectItem>
                    <SelectItem value="photo">Photo</SelectItem>
                    <SelectItem value="scan">Scan</SelectItem>
                    <SelectItem value="document">Document</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={() => pendingFile && uploadMutation.mutate(pendingFile)}
                disabled={!pendingFile || uploadMutation.isPending}
              >
                {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
              </Button>
              <Button
                variant="outline"
                className="border-primary/20 text-primary hover:bg-primary/5"
                onClick={() => setIsTwainOpen(true)}
              >
                <Camera className="mr-2 h-4 w-4" />
                Capture from Sensor
              </Button>
            </div>
            {pendingFile && <p className="text-sm text-muted-foreground">Selected: {pendingFile.name}</p>}
            {uploadMutation.isError && (
              <p className="text-sm text-destructive">
                Upload failed: {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Unknown error'}
              </p>
            )}
            {uploadMutation.isSuccess && <p className="text-sm text-emerald-600 font-medium">Image uploaded successfully.</p>}
          </CardContent>
        </Card>
      )}

      {/* Sensor Bridge Status */}
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 text-foreground">
          <div className="flex items-start sm:items-center gap-3">
            <Cpu className="h-6 w-6 text-primary flex-shrink-0 mt-1 sm:mt-0" />
            <div>
              <p className="text-sm font-semibold">Sensor Workstation Bridge &amp; DICOM Engine Active</p>
              <p className="text-xs text-muted-foreground">Direct streaming enabled for Dexis, Schick 33, Carestream RVG, Vatech EzSensor, Planmeca &amp; TWAIN-compliant devices with native DICOM Part 10 metadata tagging.</p>
            </div>
          </div>
          <Button
            size="sm"
            className="flex-shrink-0"
            onClick={() => setIsTwainOpen(true)}
            disabled={!patientId}
          >
            <Camera className="mr-1.5 h-3.5 w-3.5" /> Launch Bridge
          </Button>
        </CardContent>
      </Card>

      {/* Gallery */}
      {selectedPatient && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">
              {selectedPatient.firstName} {selectedPatient.lastName} — Imaging Records
            </CardTitle>
          </CardHeader>
          <CardContent>
            {imagesQuery.isLoading && <p className="text-sm text-muted-foreground">Loading images…</p>}
            {imagesQuery.isError && <p className="text-sm text-destructive">Unable to load images for this patient.</p>}
            {!imagesQuery.isLoading && !imagesQuery.isError && imagesQuery.data?.length === 0 && (
              <div className="py-8 text-center text-muted-foreground">
                <ImageIcon className="mx-auto h-10 w-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm font-medium">No imaging records found for this patient.</p>
                <p className="text-xs mt-1">Upload a radiograph or use Direct Sensor Capture above.</p>
              </div>
            )}
            {imagesQuery.data && imagesQuery.data.length > 0 && (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {imagesQuery.data.map((image) => (
                  <a
                    key={image.id}
                    href={image.fileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="group overflow-hidden rounded-xl border border-border bg-card hover:border-primary/50 transition-colors"
                  >
                    <div className="flex aspect-video items-center justify-center bg-muted/40 text-muted-foreground">
                      {image.fileUrl ? (
                        <img src={image.fileUrl} alt={image.title} className="h-full w-full object-cover" />
                      ) : (
                        <ImageIcon className="h-8 w-8 opacity-40" />
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-3 p-4">
                      <div>
                        <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                          {image.title}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {image.category} · {image.captureDate ? new Date(image.captureDate).toLocaleDateString() : 'Undated'}
                        </p>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

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
