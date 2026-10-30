import { useState } from 'react';
import {
  CheckCircle2,
  DollarSign,
  FileSpreadsheet,
  FileText,
  Loader2,
  Upload,
} from 'lucide-react';
import { insuranceApi } from '@/services/insuranceApi';
import { useToast } from '@/hooks/use-toast';
import { useCurrencyFormatter } from '@/hooks/useCurrencyFormatter';
import { Badge } from '@/components/ui/badge';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface EraReconciliationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onReconciled: () => void;
}

const SAMPLE_835_ERA = `ISA*00*          *00*          *ZZ*PAYER          *ZZ*SUBMITTER      *261019*1200*^*00501*000000001*0*P*:~
GS*HP*PAYER*SUBMITTER*20261019*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*150.00*C*ACH*CTX*01*999999999*DA*123456789*1999999999**01*999999999*DA*987654321*20261019~
TRN*1*CHK-20261019-99*1999999999~
N1*PR*DELTA DENTAL OF CA~
N1*PE*COREDENT PRACTICE*XX*1234567890~
CLP*CLM-SAMPLE-001*1*200.00*150.00*25.00*12*1234567890123~
CAS*CO*45*25.00~
CAS*PR*1*25.00~
SE*9*0001~
GE*1*1~
IEA*1*000000001~`;

export function EraReconciliationDialog({
  open,
  onOpenChange,
  onReconciled,
}: EraReconciliationDialogProps) {
  const { toast } = useToast();
  const { formatCurrency } = useCurrencyFormatter();
  const [activeTab, setActiveTab] = useState<'upload' | 'paste'>('paste');
  const [eraText, setEraText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [reconcileResult, setReconcileResult] = useState<any>(null);

  const resetState = () => {
    setEraText('');
    setSelectedFile(null);
    setReconcileResult(null);
    setIsProcessing(false);
  };

  const handleClose = () => {
    resetState();
    onOpenChange(false);
  };

  const handleProcessText = async () => {
    if (!eraText.trim()) {
      toast({ title: 'Input Required', description: 'Please enter ANSI X12 835 ERA content.', variant: 'destructive' });
      return;
    }

    setIsProcessing(true);
    setReconcileResult(null);
    try {
      const result = await insuranceApi.reconcileEraText(eraText);
      setReconcileResult(result);
      toast({
        title: 'ERA Reconciled',
        description: `Successfully processed Remittance #${result.remittance_check_number || 'EFT'}. ${result.matched_count} claim(s) reconciled.`,
      });
      onReconciled();
    } catch (err: any) {
      toast({
        title: 'Reconciliation Failed',
        description: err?.message || 'Failed to process 835 ERA remittance advice.',
        variant: 'destructive',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleProcessFile = async () => {
    if (!selectedFile) {
      toast({ title: 'File Required', description: 'Please select an .835 or .txt file.', variant: 'destructive' });
      return;
    }

    setIsProcessing(true);
    setReconcileResult(null);
    try {
      const result = await insuranceApi.uploadEraFile(selectedFile);
      setReconcileResult(result);
      toast({
        title: 'ERA Reconciled',
        description: `Successfully reconciled ${result.matched_count} claim(s).`,
      });
      onReconciled();
    } catch (err: any) {
      toast({
        title: 'Upload Failed',
        description: err?.message || 'Failed to parse and reconcile ERA file.',
        variant: 'destructive',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[700px]">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-emerald-100 p-2 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-xl">Reconcile 835 Remittance Advice (ERA)</DialogTitle>
              <DialogDescription>
                Adjudicate claims, interpret CARC adjustments, and auto-post insurance payments to invoices.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {!reconcileResult ? (
          <div className="space-y-4 py-2">
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="paste">
                  <FileText className="mr-2 h-4 w-4" />
                  Paste EDI 835 Text
                </TabsTrigger>
                <TabsTrigger value="upload">
                  <Upload className="mr-2 h-4 w-4" />
                  Upload .835 File
                </TabsTrigger>
              </TabsList>

              <TabsContent value="paste" className="space-y-3 pt-3">
                <div className="flex items-center justify-between">
                  <Label htmlFor="era-text" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    ANSI ASC X12 835 Remittance Stream
                  </Label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-primary"
                    onClick={() => setEraText(SAMPLE_835_ERA)}
                  >
                    Load Sample 835
                  </Button>
                </div>
                <Textarea
                  id="era-text"
                  placeholder="Paste ISA*00*...~ST*835*...~CLP*...~SE*...~ here"
                  value={eraText}
                  onChange={(e) => setEraText(e.target.value)}
                  className="font-mono text-xs h-48"
                />
              </TabsContent>

              <TabsContent value="upload" className="space-y-4 pt-3">
                <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 p-8 text-center hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                  <FileSpreadsheet className="mb-2 h-10 w-10 text-muted-foreground/60" />
                  <p className="text-sm font-medium">Select ANSI ASC X12 835 file from clearinghouse</p>
                  <p className="text-xs text-muted-foreground mt-1">Accepts .835, .txt, or .edi files</p>
                  <input
                    type="file"
                    accept=".835,.txt,.edi"
                    className="hidden"
                    id="era-file-input"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => document.getElementById('era-file-input')?.click()}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Browse Files
                  </Button>
                  {selectedFile && (
                    <div className="mt-3 inline-flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-950/50 px-3 py-1 text-xs text-emerald-700 dark:text-emerald-300 font-medium">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <div className="space-y-4 py-2">
            <Alert className="border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <AlertTitle className="text-emerald-900 dark:text-emerald-200 font-semibold">
                835 Remittance Processed Successfully
              </AlertTitle>
              <AlertDescription className="text-emerald-800 dark:text-emerald-300 text-xs">
                Check/Trace: <strong>{reconcileResult.remittance_check_number || 'EFT'}</strong> ·
                Payer: <strong>{reconcileResult.payer_name || 'Unknown'}</strong> ·
                Method: <strong>{reconcileResult.payment_method || 'ACH'}</strong>
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Total Remittance</p>
                <p className="text-base font-bold text-slate-900 dark:text-slate-100">
                  {formatCurrency(reconcileResult.total_remittance_amount || 0)}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Posted to Ledger</p>
                <p className="text-base font-bold text-emerald-600 dark:text-emerald-400">
                  {formatCurrency(reconcileResult.total_posted_to_ledger || 0)}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Matched Claims</p>
                <p className="text-base font-bold text-blue-600 dark:text-blue-400">
                  {reconcileResult.matched_count}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Unmatched</p>
                <p className="text-base font-bold text-amber-600 dark:text-amber-400">
                  {reconcileResult.unmatched_count}
                </p>
              </div>
            </div>

            {reconcileResult.reconciled_claims?.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Reconciled Claims & Ledger Postings
                </h4>
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {reconcileResult.reconciled_claims.map((claim: any, idx: number) => (
                    <div key={idx} className="rounded-lg border p-3 text-xs space-y-1.5 bg-slate-50/50 dark:bg-slate-900/50">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          Claim #{claim.claim_number}
                        </span>
                        <Badge variant="outline" className="text-emerald-700 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-300">
                          {claim.adjudicated_status.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between text-muted-foreground">
                        <span>Billed: {formatCurrency(claim.billed_amount)}</span>
                        <span className="font-medium text-emerald-600">Paid: {formatCurrency(claim.paid_amount)}</span>
                        <span>Patient Resp: {formatCurrency(claim.patient_responsibility)}</span>
                        <span>Adj: {formatCurrency(claim.contractual_adjustment)}</span>
                      </div>
                      {claim.carc_codes?.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {claim.carc_codes.map((carc: any, cIdx: number) => (
                            <span key={cIdx} className="rounded bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-700 dark:text-slate-300">
                              CARC {carc.group}-{carc.code}: {formatCurrency(carc.amount)}
                            </span>
                          ))}
                        </div>
                      )}
                      {claim.posted_payment_id && (
                        <p className="text-[11px] text-emerald-700 dark:text-emerald-400 flex items-center gap-1 pt-0.5">
                          <CheckCircle2 className="h-3 w-3" /> Auto-posted payment ID: {claim.posted_payment_id}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {reconcileResult.unmatched_claims?.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                  Unmatched Claims ({reconcileResult.unmatched_claims.length})
                </h4>
                <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                  {reconcileResult.unmatched_claims.map((unmatched: any, idx: number) => (
                    <div key={idx} className="rounded border border-amber-200 bg-amber-50/50 dark:bg-amber-950/20 p-2 text-xs">
                      Claim #{unmatched.claim_number} — Paid: {formatCurrency(unmatched.paid_amount || 0)} (No matching claim found in practice)
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          {!reconcileResult ? (
            <>
              <Button variant="ghost" onClick={handleClose} disabled={isProcessing}>
                Cancel
              </Button>
              <Button
                onClick={activeTab === 'paste' ? handleProcessText : handleProcessFile}
                disabled={isProcessing || (activeTab === 'paste' ? !eraText.trim() : !selectedFile)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Reconciling ERA…
                  </>
                ) : (
                  <>
                    <DollarSign className="mr-2 h-4 w-4" />
                    Reconcile & Auto-Post
                  </>
                )}
              </Button>
            </>
          ) : (
            <div className="flex w-full items-center justify-between">
              <Button variant="outline" size="sm" onClick={() => setReconcileResult(null)}>
                Reconcile Another
              </Button>
              <Button onClick={handleClose} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                Done
              </Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
