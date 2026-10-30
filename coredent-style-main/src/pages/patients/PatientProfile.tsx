// ============================================
// CoreDent PMS - Patient Profile Page
// Comprehensive view of patient records
// ============================================

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/auth-context';
import { 
  Tabs, 
  TabsContent, 
  TabsList, 
  TabsTrigger 
} from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertTriangle, ChevronRight, CalendarPlus, Download, Loader2 } from 'lucide-react';

// Components & Hooks
import { patientsApi } from '@/services/api';
import { patientApi, type PatientAppointmentHistoryItem } from '@/services/patientApi';
import { useApiRequest } from '@/hooks/useApiRequest';
import { PatientProfileHeader } from '@/components/patients/PatientProfileHeader';
import { PatientQuickStats } from '@/components/patients/PatientQuickStats';
import { PatientOverviewTab } from '@/components/patients/PatientOverviewTab';
import { PatientMedicalTab } from '@/components/patients/PatientMedicalTab';
import { PatientDialog } from '@/components/patients/PatientDialog';
import { AddNoteDialog } from '@/components/patients/AddNoteDialog';
import { AnonymizePatientDialog } from '@/components/patients/AnonymizePatientDialog';
import { AppointmentHistory } from '@/components/patients/AppointmentHistory';
import { AttachmentsList } from '@/components/patients/AttachmentsList';
import { Eraser } from 'lucide-react';
import type { PatientRecord } from '@/types/patient';
import type { ApiResponse } from '@/types/api';

export default function PatientProfile() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');
  
  // Dialog States
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isAddNoteDialogOpen, setIsAddNoteDialogOpen] = useState(false);
  const [isAnonymizeOpen, setIsAnonymizeOpen] = useState(false);

  // Region Config (US vs INDIA)
  const region = user?.practiceCountry || 'US';

  // Memoized Fetcher
  const fetchPatient = useCallback(
    () => patientsApi.getById(id!) as Promise<ApiResponse<PatientRecord>>,
    [id],
  );

  // Stable options object: inline object literals here previously gave the
  // useApiRequest `execute` callback a fresh dependency every render, which
  // made the load effect below refetch forever.
  const loadOptions = useMemo(
    () => ({ errorMessage: 'Failed to load patient profile' }),
    [],
  );

  // API Hooks
  const {
    data: patient,
    isLoading,
    error,
    execute: loadPatient,
    setData: setPatient
  } = useApiRequest<PatientRecord>(fetchPatient, loadOptions);

  const { execute: updateStatus } = useApiRequest<PatientRecord>(
    ((status: unknown) =>
      patientsApi.update(id!, { status: status as 'active' | 'inactive' }) as Promise<ApiResponse<PatientRecord>>),
    {
      successMessage: 'Patient status updated',
      onSuccess: (updated) => setPatient(updated as PatientRecord)
    }
  );

  const { execute: exportData, isLoading: isExporting } = useApiRequest<any>(
    (() => patientsApi.exportData(id!) as Promise<any>),
    {
      successMessage: 'Patient data exported successfully',
      errorMessage: 'Failed to export patient data',
      onSuccess: (data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `patient-export-${patient?.firstName || 'Unknown'}-${patient?.lastName || 'Patient'}-${id}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    }
  );

  useEffect(() => {
    if (id) {
      loadPatient();
    } else {
      navigate('/patients');
    }
  }, [id, loadPatient, navigate]);

  // Appointment history for the Appointments tab (real data via the
  // patient-filtered appointments list — previously hardcoded to []).
  const [appointmentHistory, setAppointmentHistory] = useState<PatientAppointmentHistoryItem[]>([]);
  const [isLoadingAppointments, setIsLoadingAppointments] = useState(false);

  useEffect(() => {
    if (!id) return;
    let isActive = true;
    const loadHistory = async () => {
      setIsLoadingAppointments(true);
      try {
        const history = await patientApi.getAppointmentHistory(id);
        if (isActive) setAppointmentHistory(history);
      } catch {
        if (isActive) setAppointmentHistory([]);
      } finally {
        if (isActive) setIsLoadingAppointments(false);
      }
    };
    loadHistory();
    return () => {
      isActive = false;
    };
  }, [id]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
        <Skeleton className="h-[400px] rounded-xl" />
      </div>
    );
  }

  if (error || !patient) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          {error || 'Patient not found. Re-directing...'}
        </AlertDescription>
      </Alert>
    );
  }

  const handleStatusChange = () => {
    const newStatus = patient.status === 'active' ? 'inactive' : 'active';
    updateStatus(newStatus);
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between gap-4">
        <nav className="flex items-center gap-1 text-sm text-muted-foreground">
          <Link to="/patients" className="hover:text-foreground transition-colors">Patients</Link>
          <ChevronRight className="h-4 w-4" />
          <span className="text-foreground font-medium">
            {patient.firstName} {patient.lastName}
          </span>
        </nav>
        <div className="flex items-center gap-2">
          {user?.role && ['owner', 'admin'].includes(user.role.toLowerCase()) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => exportData()}
              disabled={isExporting}
              className="flex items-center gap-2"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              GDPR Export
            </Button>
          )}
          {user?.role && ['owner', 'admin'].includes(user.role.toLowerCase()) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsAnonymizeOpen(true)}
              className="flex items-center gap-2 border-destructive/50 text-destructive hover:bg-destructive/10"
              title="Permanently erase this patient's personal data (GDPR right-to-erasure). Billing records are retained anonymized."
            >
              <Eraser className="h-4 w-4" />
              GDPR Erase
            </Button>
          )}
          {/* Patient NAME is deliberately not placed in the URL: query strings
              persist in history, are exposed to Referer and are logged by every
              intermediary, and nothing consumed it (Schedule never read it). */}
          <Button
            size="sm"
            onClick={() => navigate(`/schedule?patientId=${patient.id}`)}
            className="flex items-center gap-2"
          >
            <CalendarPlus className="h-4 w-4" />
            Schedule Appointment
          </Button>
        </div>
      </div>

      <PatientProfileHeader 
        patient={patient} 
        onEdit={() => setIsEditDialogOpen(true)} 
        onStatusChange={handleStatusChange} 
        region={region}
      />

      {patient.medicalHistory?.allergies?.length > 0 && (
        <Alert variant="destructive" className="bg-red-50 border-red-200">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertTitle className="text-red-800 font-bold">Medical Alert: Allergies</AlertTitle>
          <AlertDescription className="text-red-700">
            {patient.medicalHistory.allergies.join(', ')}
          </AlertDescription>
        </Alert>
      )}

      <PatientQuickStats 
        stats={patient.appointmentStats} 
        notesCount={patient.notes?.length ?? 0} 
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start border-b rounded-none h-auto p-0 bg-transparent">
          <TabsTrigger value="overview" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Overview</TabsTrigger>
          <TabsTrigger value="medical" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Medical/Dental</TabsTrigger>
          <TabsTrigger value="appointments" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Appointments</TabsTrigger>
          <TabsTrigger value="files" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Files & Images</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <PatientOverviewTab 
            patient={patient} 
            onAddNote={() => setIsAddNoteDialogOpen(true)} 
          />
        </TabsContent>

        <TabsContent value="medical" className="mt-6">
          <PatientMedicalTab 
            medicalHistory={patient.medicalHistory} 
            dentalHistory={patient.dentalHistory} 
          />
        </TabsContent>

        <TabsContent value="appointments" className="mt-6">
          {isLoadingAppointments ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24 rounded-xl" />
              ))}
            </div>
          ) : (
            <AppointmentHistory appointments={appointmentHistory} />
          )}
        </TabsContent>

        <TabsContent value="files" className="mt-6">
          <AttachmentsList 
            patientId={patient.id}
            attachments={patient.attachments ?? []} 
            onUpload={() => loadPatient()}
            onDelete={() => loadPatient()}
          />
        </TabsContent>
      </Tabs>

      <PatientDialog 
        open={isEditDialogOpen} 
        onOpenChange={setIsEditDialogOpen} 
        patient={patient}
        onSave={() => loadPatient()}
        region={region}
      />

      <AddNoteDialog 
        open={isAddNoteDialogOpen} 
        onOpenChange={setIsAddNoteDialogOpen} 
        patientId={patient.id}
        onSave={() => loadPatient()}
      />

      <AnonymizePatientDialog
        open={isAnonymizeOpen}
        onOpenChange={setIsAnonymizeOpen}
        patient={patient}
        onAnonymized={() => {
          setIsAnonymizeOpen(false);
          navigate('/patients', { replace: true });
        }}
      />
    </div>
  );
}
