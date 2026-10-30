// ============================================
// CoreDent PMS - Dental Chart Page
// Interactive dental charting interface
// ============================================

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';
import { DentalChartView } from '@/components/chart/DentalChartView';
import { ToothDetailsPanel } from '@/components/chart/ToothDetailsPanel';
import { AddProcedureDialog } from '@/components/chart/AddProcedureDialog';
import { AIClinicalAssistant } from '@/components/chart/AIClinicalAssistant';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertTriangle, RefreshCw, User } from 'lucide-react';
import { dentalChartApi } from '@/services/dentalChartApi';
import type { 
  DentalChart as DentalChartType, 
  ToothCondition, 
  ProcedureStatus,
} from '@/types/dentalChart';

export default function DentalChart() {
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  
  // State
  const [chart, setChart] = useState<DentalChartType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [selectedToothNumber, setSelectedToothNumber] = useState<number | null>(null);
  const [isAddProcedureOpen, setIsAddProcedureOpen] = useState(false);
  
  // Get patient ID from URL or use default
  const patientId = searchParams.get('patientId');

  // Load chart data
  useEffect(() => {
    if (!patientId) {
      setChart(null);
      setLoadError(new Error('No patient was selected for this chart.'));
      setIsLoading(false);
      toast({
        title: 'Missing patient',
        description: 'No patient was selected for this chart.',
        variant: 'destructive',
      });
      return;
    }

    async function loadChart() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await dentalChartApi.getChart(patientId as string);
        setChart(data);
      } catch (cause) {
        const nextError = cause instanceof Error ? cause : new Error('Failed to load dental chart data');
        setChart(null);
        setLoadError(nextError);
        toast({
          title: 'Error loading chart',
          description: 'Failed to load dental chart data',
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    }
    loadChart();
  }, [patientId, toast]);

  // Get selected tooth data
  const selectedTooth = chart?.teeth.find(t => t.number === selectedToothNumber) || null;

  // Handle tooth selection
  const handleSelectTooth = (toothNumber: number) => {
    setSelectedToothNumber(prev => prev === toothNumber ? null : toothNumber);
  };

  // Handle condition update
  const handleUpdateCondition = async (condition: ToothCondition) => {
    if (!patientId || !selectedToothNumber || !chart) return;
    
    try {
      await dentalChartApi.updateToothCondition(patientId, selectedToothNumber, condition);
      
      // Update local state
      setChart(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          teeth: prev.teeth.map(t =>
            t.number === selectedToothNumber ? { ...t, condition } : t
          ),
        };
      });
      
      toast({
        title: 'Condition updated',
        description: `Tooth #${selectedToothNumber} condition set to ${condition}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to update tooth condition',
        variant: 'destructive',
      });
    }
  };

  // Handle add procedure
  const handleAddProcedure = async (data: {
    code: string;
    description: string;
    surface?: string;
    cost: number;
    notes?: string;
    status: ProcedureStatus;
    date: string;
  }) => {
    if (!patientId || !selectedToothNumber || !chart) return;
    
    try {
      const newProcedure = await dentalChartApi.addProcedure(
        patientId,
        selectedToothNumber,
        {
          code: data.code,
          description: data.description,
          surface: data.surface,
          cost: data.cost,
          status: data.status,
          date: data.date,
          notes: data.notes,
        },
      );
      
      // Update local state
      setChart(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          teeth: prev.teeth.map(t =>
            t.number === selectedToothNumber
              ? { ...t, procedures: [...(t.procedures ?? []), newProcedure] }
              : t
          ),
        };
      });
      
      toast({
        title: 'Procedure added',
        description: `${data.description} added to tooth #${selectedToothNumber}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to add procedure',
        variant: 'destructive',
      });
    }
  };

  // Handle procedure status update
  const handleUpdateProcedureStatus = async (procedureId: string, status: ProcedureStatus) => {
    if (!patientId || !selectedToothNumber || !chart) return;
    
    try {
      await dentalChartApi.updateProcedureStatus(patientId, selectedToothNumber, procedureId, status);
      
      // Update local state
      setChart(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          teeth: prev.teeth.map(t =>
            t.number === selectedToothNumber
              ? {
                  ...t,
                  procedures: (t.procedures ?? []).map(p =>
                    p.id === procedureId ? { ...p, status } : p
                  ),
                }
              : t
          ),
        };
      });
      
      toast({
        title: 'Status updated',
        description: `Procedure status changed to ${status}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to update procedure status',
        variant: 'destructive',
      });
    }
  };

  // Handle procedure deletion
  const handleDeleteProcedure = async (procedureId: string) => {
    if (!patientId || !selectedToothNumber || !chart) return;
    
    try {
      await dentalChartApi.deleteProcedure(patientId, selectedToothNumber, procedureId);
      
      // Update local state
      setChart(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          teeth: prev.teeth.map(t =>
            t.number === selectedToothNumber
              ? {
                  ...t,
                  procedures: (t.procedures ?? []).filter(p => p.id !== procedureId),
                }
              : t
          ),
        };
      });
      
      toast({
        title: 'Procedure deleted',
        description: 'Procedure has been removed from the chart',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete procedure',
        variant: 'destructive',
      });
    }
  };

  // Refresh chart
  const handleRefresh = async () => {
    if (!patientId) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await dentalChartApi.getChart(patientId);
      setChart(data);
      setSelectedToothNumber(null);
      toast({
        title: 'Chart refreshed',
        description: 'Dental chart data has been reloaded',
      });
    } catch (cause) {
      const nextError = cause instanceof Error ? cause : new Error('Failed to refresh chart');
      setLoadError(nextError);
      toast({
        title: 'Error',
        description: 'Failed to refresh chart',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Dental Chart</h1>
          <p className="text-muted-foreground">
            Interactive tooth charting and procedure tracking
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {loadError && (
        <Alert variant="destructive" role="alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Dental chart unavailable</AlertTitle>
          <AlertDescription>{loadError.message}</AlertDescription>
        </Alert>
      )}

      {/* Patient info bar */}
      {chart && (
        <Card>
          <CardContent className="py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <User className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium">{chart.patientName ?? `Patient ${chart.patientId.slice(0, 8)}`}</p>
                <p className="text-sm text-muted-foreground">
                  Last updated:{' '}
                  {/* Explicit locale and options: toLocaleDateString() with no
                      arguments resolves against the host's locale, so this
                      rendered as 20/6/2026 on one machine and 6/20/2026 on
                      another. That made it both inconsistent for support and
                      untestable - the assertion passed locally and failed on
                      CI. Pinned to an unambiguous day/month/year form. */}
                  {new Date(chart.lastUpdated ?? chart.updatedAt).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'numeric',
                    year: 'numeric',
                  })}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main content */}
      {isLoading ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Skeleton className="h-[400px] w-full rounded-xl" />
          </div>
          <div>
            <Skeleton className="h-[400px] w-full rounded-xl" />
          </div>
        </div>
      ) : chart ? (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Chart view */}
          <div className="lg:col-span-2">
            <DentalChartView
              teeth={chart.teeth}
              selectedTooth={selectedToothNumber}
              onSelectTooth={handleSelectTooth}
            />
          </div>
          
          {/* Details panel */}
          <div>
            <ToothDetailsPanel
              tooth={selectedTooth}
              onAddProcedure={() => setIsAddProcedureOpen(true)}
              onUpdateCondition={handleUpdateCondition}
              onUpdateProcedureStatus={handleUpdateProcedureStatus}
              onDeleteProcedure={handleDeleteProcedure}
            />
            <div className="mt-6">
              <AIClinicalAssistant onApplyFinding={(tooth, finding) => {
                 setSelectedToothNumber(tooth);
                 toast({ title: "AI Finding Applied", description: `Updated tooth #${tooth} with: ${finding}` });
              }} />
            </div>
          </div>
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No chart data available</p>
          </CardContent>
        </Card>
      )}

      {/* Add procedure dialog */}
      {selectedTooth && (
        <AddProcedureDialog
          open={isAddProcedureOpen}
          onOpenChange={setIsAddProcedureOpen}
          toothNumber={selectedTooth.number}
          toothName={selectedTooth.name}
          onSubmit={handleAddProcedure}
        />
      )}
    </div>
  );
}
