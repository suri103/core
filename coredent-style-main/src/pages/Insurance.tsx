import React, { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Calendar, Download, FileSpreadsheet, Loader2, Plus, RefreshCw, Search, Send, Shield } from 'lucide-react';
import { insuranceApi } from '@/services/insuranceApi';
import type { ClaimStatus, InsuranceClaim } from '@/types/insurance';
import { useToast } from '@/hooks/use-toast';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { EraReconciliationDialog } from '@/components/insurance/EraReconciliationDialog';

const PAGE_SIZE = 50;

const statusConfig: Record<ClaimStatus, { label: string; className: string }> = {
  draft: { label: 'Draft', className: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' },
  pending: { label: 'Pending', className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  submitting: { label: 'Submitting', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  submitted: { label: 'Submitted', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  in_review: { label: 'In review', className: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' },
  approved: { label: 'Approved', className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  partially_approved: { label: 'Partially approved', className: 'bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400' },
  denied: { label: 'Denied', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  paid: { label: 'Paid', className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  appealed: { label: 'Appealed', className: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400' },
  submission_failed: { label: 'Submission failed', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
};

interface NewClaimDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

function NewClaimDialog({ open, onOpenChange, onCreated }: NewClaimDialogProps) {
  const { toast } = useToast();
  const [patientInsuranceId, setPatientInsuranceId] = useState('');
  const [serviceDate, setServiceDate] = useState('');
  const [procedureCode, setProcedureCode] = useState('');
  const [description, setDescription] = useState('');
  const [fee, setFee] = useState('');
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const reset = () => {
    setPatientInsuranceId('');
    setServiceDate('');
    setProcedureCode('');
    setDescription('');
    setFee('');
    setNotes('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const billedAmount = Number(fee);
    if (!patientInsuranceId || !serviceDate || !procedureCode || !description || !Number.isFinite(billedAmount) || billedAmount <= 0) {
      return;
    }

    setIsSaving(true);
    try {
      await insuranceApi.createClaim({
        patientInsuranceId,
        serviceDate,
        billedAmount,
        procedureCodes: [{ code: procedureCode, description, fee: billedAmount }],
        notes: notes || undefined,
      });
      toast({ title: 'Claim Created', description: 'The draft claim was created.' });
      reset();
      onOpenChange(false);
      onCreated();
    } catch {
      toast({ title: 'Error', description: 'Failed to create claim', variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader><DialogTitle>New Insurance Claim</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="claim-policy-id">Patient insurance policy ID *</Label>
            <Input id="claim-policy-id" value={patientInsuranceId} onChange={event => setPatientInsuranceId(event.target.value)} required />
            <p className="text-xs text-muted-foreground">Use the policy ID from the patient’s insurance record.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="claim-service-date">Service date *</Label>
            <Input id="claim-service-date" type="date" value={serviceDate} onChange={event => setServiceDate(event.target.value)} required />
          </div>
          <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
            <p className="text-sm font-semibold text-muted-foreground">Procedure</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="claim-procedure-code">Code *</Label>
                <Input id="claim-procedure-code" value={procedureCode} onChange={event => setProcedureCode(event.target.value)} required />
              </div>
              <div className="space-y-1">
                <Label htmlFor="claim-fee">Billed amount *</Label>
                <Input id="claim-fee" type="number" min="0.01" step="0.01" value={fee} onChange={event => setFee(event.target.value)} required />
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="claim-description">Description *</Label>
              <Input id="claim-description" value={description} onChange={event => setDescription(event.target.value)} required />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="claim-notes">Notes</Label>
            <Textarea id="claim-notes" rows={2} value={notes} onChange={event => setNotes(event.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>Cancel</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving…</> : <><Plus className="mr-2 h-4 w-4" />Create Draft</>}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ClaimRow({
  claim,
  onSubmit,
  isSubmitting,
  onExport837D,
  isExporting,
}: {
  claim: InsuranceClaim;
  onSubmit: (id: string) => void;
  isSubmitting: boolean;
  onExport837D: (claim: InsuranceClaim) => void;
  isExporting: boolean;
}) {
  const { formatCurrency } = useCurrencyFormatter();
  const status = statusConfig[claim.status];

  return (
    <div className="flex flex-col justify-between gap-3 rounded-xl border p-4 transition-colors hover:bg-accent/30 sm:flex-row sm:items-center">
      <div className="flex items-start gap-4 min-w-0">
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"><Shield className="h-5 w-5 text-primary" /></div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-semibold truncate">Claim {claim.claimNumber}</p>
            {claim.ediTransactionId && (
              <Badge variant="outline" className="text-[10px] h-4 px-1 text-blue-600 border-blue-200">
                EDI
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">Patient ID: {claim.patientId} · Carrier ID: {claim.carrierId}</p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />Service: {new Date(`${claim.serviceDate}T00:00:00`).toLocaleDateString()}
            {claim.submissionDate && <> · Submitted: {new Date(`${claim.submissionDate}T00:00:00`).toLocaleDateString()}</>}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 sm:shrink-0">
        <div className="min-w-[80px] text-right">
          <p className="text-sm font-semibold">{formatCurrency(claim.billedAmount)}</p>
          <p className="text-xs text-muted-foreground">Paid: {formatCurrency(claim.paidAmount)}</p>
        </div>
        <Badge className={`${status.className} border-none text-xs`}>{status.label}</Badge>
        <Button
          size="sm"
          variant="outline"
          className="h-8 gap-1 text-xs"
          title="Export ANSI ASC X12 837D Dental Claim batch"
          onClick={() => onExport837D(claim)}
          disabled={isExporting}
        >
          <Download className="h-3 w-3" />
          {isExporting ? 'Exporting…' : '837D'}
        </Button>
        {claim.status === 'draft' && (
          <Button size="sm" variant="default" className="h-8 gap-1 text-xs" onClick={() => onSubmit(claim.id)} disabled={isSubmitting}>
            <Send className="h-3 w-3" />Submit
          </Button>
        )}
      </div>
    </div>
  );
}

export default function Insurance() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ClaimStatus | 'all'>('all');
  const [claimOffset, setClaimOffset] = useState(0);
  const [preAuthOffset, setPreAuthOffset] = useState(0);
  const [isNewClaimOpen, setIsNewClaimOpen] = useState(false);
  const [isEraOpen, setIsEraOpen] = useState(false);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);

  const carriersQuery = useQuery({
    queryKey: ['insurance', 'carriers'],
    queryFn: () => insuranceApi.getCarriers(),
    staleTime: 5 * 60 * 1000,
  });
  const claimsQuery = useQuery({
    queryKey: ['insurance', 'claims', statusFilter, claimOffset],
    queryFn: () => insuranceApi.getClaims({
      status: statusFilter === 'all' ? undefined : statusFilter,
      limit: PAGE_SIZE,
      offset: claimOffset,
    }),
    staleTime: 5 * 60 * 1000,
  });
  const preAuthQuery = useQuery({
    queryKey: ['insurance', 'preAuths', preAuthOffset],
    queryFn: () => insuranceApi.getPreAuthorizations({
      limit: PAGE_SIZE,
      offset: preAuthOffset,
    }),
    staleTime: 5 * 60 * 1000,
  });

  const carriers = carriersQuery.data ?? [];
  const claimsPage = claimsQuery.data;
  const claims = useMemo(() => claimsPage?.items ?? [], [claimsPage]);
  const preAuthPage = preAuthQuery.data;
  const preAuths = preAuthPage?.items ?? [];
  const isLoading = carriersQuery.isLoading || claimsQuery.isLoading || preAuthQuery.isLoading;
  const hasInsuranceError = carriersQuery.isError || claimsQuery.isError || preAuthQuery.isError;

  const filteredClaims = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return claims;
    return claims.filter(claim =>
      claim.claimNumber.toLowerCase().includes(query) ||
      claim.patientId.toLowerCase().includes(query) ||
      claim.carrierId.toLowerCase().includes(query),
    );
  }, [claims, searchQuery]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['insurance'] });

  const handleSubmitClaim = async (claimId: string) => {
    setSubmittingId(claimId);
    try {
      await insuranceApi.submitClaim(claimId);
      toast({ title: 'Claim Submitted', description: 'The claim was sent to the configured clearinghouse.' });
      refresh();
    } catch {
      toast({ title: 'Error', description: 'Failed to submit claim.', variant: 'destructive' });
    } finally {
      setSubmittingId(null);
    }
  };

  const handleExport837D = async (claim: InsuranceClaim) => {
    setExportingId(claim.id);
    try {
      const res = await insuranceApi.export837DClaim(claim.id);
      const content = typeof res === 'string' ? res : (res as any)?.edi_content || JSON.stringify(res, null, 2);
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `claim_${claim.claimNumber}_837D.x12`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast({
        title: '837D Exported',
        description: `Downloaded ANSI ASC X12 837D Dental Claim batch for #${claim.claimNumber}.`,
      });
    } catch (err: any) {
      toast({
        title: 'Export Failed',
        description: err?.message || 'Failed to generate ANSI X12 837D claim batch.',
        variant: 'destructive',
      });
    } finally {
      setExportingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-bold">Insurance</h1>
          <p className="text-muted-foreground">Manage claims, clearinghouse EDI 837/835, carriers, and pre-authorizations</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />Refresh
          </Button>
          <Button
            variant="outline"
            className="border-emerald-200 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-950/40"
            onClick={() => setIsEraOpen(true)}
          >
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Reconcile 835 ERA
          </Button>
          <Button onClick={() => setIsNewClaimOpen(true)}><Plus className="mr-2 h-4 w-4" />New Claim</Button>
        </div>
      </div>

      {hasInsuranceError && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Insurance data unavailable</AlertTitle>
          <AlertDescription>One or more insurance resources could not be loaded. Unavailable data is not shown as zero activity.</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="claims">
        <TabsList>
          <TabsTrigger value="claims">Claims</TabsTrigger>
          <TabsTrigger value="coverage">Carriers & Pre-Authorizations</TabsTrigger>
        </TabsList>

        <TabsContent value="claims" className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative max-w-sm flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search loaded claims by claim, patient, or carrier ID" value={searchQuery} onChange={event => setSearchQuery(event.target.value)} className="pl-9" />
            </div>
            <Select value={statusFilter} onValueChange={value => { setStatusFilter(value as ClaimStatus | 'all'); setClaimOffset(0); }}>
              <SelectTrigger className="w-[190px]"><SelectValue placeholder="All statuses" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {Object.entries(statusConfig).map(([value, config]) => <SelectItem key={value} value={value}>{config.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {claimsQuery.isLoading ? (
            <div className="space-y-3">{[1, 2, 3].map(item => <Skeleton key={item} className="h-20 rounded-xl" />)}</div>
          ) : filteredClaims.length === 0 ? (
            <Card><CardContent className="py-16 text-center"><Shield className="mx-auto mb-4 h-12 w-12 text-muted-foreground/40" /><h2 className="text-lg font-semibold">No claims found</h2></CardContent></Card>
          ) : (
            <div className="space-y-3">
              {filteredClaims.map(claim => (
                <ClaimRow
                  key={claim.id}
                  claim={claim}
                  onSubmit={handleSubmitClaim}
                  isSubmitting={submittingId === claim.id}
                  onExport837D={handleExport837D}
                  isExporting={exportingId === claim.id}
                />
              ))}
              {claimsPage && (
                <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
                  <span>Showing {claimsPage.offset + 1}–{claimsPage.offset + claimsPage.count} of {claimsPage.total}</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={claimsPage.offset === 0} onClick={() => setClaimOffset(Math.max(0, claimsPage.offset - claimsPage.limit))}>Previous</Button>
                    <Button size="sm" variant="outline" disabled={claimsPage.nextOffset === null} onClick={() => claimsPage.nextOffset !== null && setClaimOffset(claimsPage.nextOffset)}>Next</Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="coverage" className="space-y-6">
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Insurance Carriers</h2>
            {carriersQuery.isLoading ? (
              <div className="space-y-3">{[1, 2, 3].map(item => <Skeleton key={item} className="h-16 rounded-xl" />)}</div>
            ) : carriers.length === 0 ? (
              <Card><CardContent className="py-12 text-center text-muted-foreground">No insurance carriers configured.</CardContent></Card>
            ) : carriers.map(carrier => (
              <div key={carrier.id} className="flex items-center justify-between gap-3 rounded-xl border p-4">
                <div><p className="font-semibold">{carrier.name}</p><p className="text-xs text-muted-foreground">Carrier ID: {carrier.id}{carrier.payerId ? ` · Payer ID: ${carrier.payerId}` : ''}</p></div>
                <Badge className={carrier.isActive ? 'border-none bg-green-100 text-green-700' : 'border-none bg-gray-100 text-gray-600'}>{carrier.isActive ? 'Active' : 'Inactive'}</Badge>
              </div>
            ))}
          </section>

          <section className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold">Pre-Authorizations</h2>
              {preAuthPage && <p className="text-xs text-muted-foreground">Showing {preAuthPage.count} of {preAuthPage.total}</p>}
            </div>
            {preAuthQuery.isLoading ? (
              <div className="space-y-3">{[1, 2].map(item => <Skeleton key={item} className="h-16 rounded-xl" />)}</div>
            ) : preAuths.length === 0 ? (
              <Card><CardContent className="py-12 text-center text-muted-foreground">No pre-authorizations found.</CardContent></Card>
            ) : (
              <div className="space-y-3">
                {preAuths.map(preAuth => (
                  <div key={preAuth.id} className="flex items-center justify-between gap-3 rounded-xl border p-4">
                    <div>
                      <p className="font-medium">Authorization {preAuth.authorizationNumber}</p>
                      <p className="text-xs text-muted-foreground">Patient ID: {preAuth.patientId} · Policy ID: {preAuth.patientInsuranceId}</p>
                      <p className="text-xs text-muted-foreground">Procedures: {preAuth.procedureCodes.map(procedure => procedure.code).join(', ')}</p>
                    </div>
                    <Badge className={preAuth.status === 'approved' ? 'border-none bg-green-100 text-green-700' : preAuth.status === 'denied' ? 'border-none bg-red-100 text-red-700' : 'border-none bg-amber-100 text-amber-700'}>{preAuth.status === 'pending' ? 'Pending' : preAuth.status === 'approved' ? 'Approved' : 'Denied'}</Badge>
                  </div>
                ))}
                {preAuthPage && (
                  <div className="flex justify-end gap-2 pt-1">
                    <Button size="sm" variant="outline" disabled={preAuthPage.offset === 0} onClick={() => setPreAuthOffset(Math.max(0, preAuthPage.offset - preAuthPage.limit))}>Previous</Button>
                    <Button size="sm" variant="outline" disabled={preAuthPage.nextOffset === null} onClick={() => preAuthPage.nextOffset !== null && setPreAuthOffset(preAuthPage.nextOffset)}>Next</Button>
                  </div>
                )}
              </div>
            )}
          </section>
        </TabsContent>
      </Tabs>

      <NewClaimDialog open={isNewClaimOpen} onOpenChange={setIsNewClaimOpen} onCreated={refresh} />
      <EraReconciliationDialog open={isEraOpen} onOpenChange={setIsEraOpen} onReconciled={refresh} />
    </div>
  );
}
