import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Upload, 
  FileDown, 
  CheckCircle2, 
  Database, 
  Loader2, 
  ArrowRight, 
  FileSpreadsheet,
  AlertTriangle,
  Layers,
  Sparkles
} from "lucide-react";
import { apiClient } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { useCurrencyFormatter } from "@/hooks/useCurrencyFormatter";

type EhrSystem = "auto" | "opendental" | "dentrix" | "eaglesoft" | "generic";

interface MigrationAnalysis {
  source_system: string;
  total_rows: number;
  valid_count: number;
  duplicate_count: number;
  error_count: number;
  errors: string[];
  duplicates: string[];
  total_historical_procedure_fees?: number;
  preview: Array<{
    first_name: string;
    last_name: string;
    date_of_birth: string;
    email?: string;
    phone?: string;
    historical_procedure_count?: number;
    total_procedure_fees?: number;
  }>;
}

interface MigrationExecutionResult {
  success: boolean;
  source_system: string;
  imported_patients: number;
  imported_procedures: number;
  imported_appointments: number;
  total_historical_procedure_fees: number;
  message: string;
}

export default function DataMigration() {
  const { toast } = useToast();
  const { formatCurrency } = useCurrencyFormatter();
  const [selectedEhr, setSelectedEhr] = useState<EhrSystem>("auto");
  const [isProcessing, setIsProcessing] = useState(false);
  const [analysisData, setAnalysisData] = useState<MigrationAnalysis | null>(null);
  const [stagedRows, setStagedRows] = useState<any[]>([]);
  const [executionResult, setExecutionResult] = useState<MigrationExecutionResult | null>(null);

  const ehrOptions: Array<{ id: EhrSystem; label: string; sub: string }> = [
    { id: "auto", label: "Auto-Detect EHR", sub: "Inspects headers automatically" },
    { id: "opendental", label: "Open Dental", sub: "PatNum, ProcedureLog schema" },
    { id: "dentrix", label: "Dentrix G4-G7", sub: "ChartNumber, ProcCode schema" },
    { id: "eaglesoft", label: "Patterson Eaglesoft", sub: "PatientID, ServiceCode schema" },
    { id: "generic", label: "CoreDent CSV", sub: "Standard direct format" },
  ];

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    setAnalysisData(null);
    setExecutionResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_system", selectedEhr);

      // Call Stage 1: File Analysis API
      const response = await apiClient.post<MigrationAnalysis>("/migration/analyze-file", formData);
      const data = (response as any)?.data || response;
      setAnalysisData(data);

      // Also parse client-side rows for transactional commit execution
      const text = await file.text();
      const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
      if (lines.length > 1) {
        const headers = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
        const rows: any[] = [];
        for (let i = 1; i < lines.length; i++) {
          const parts = lines[i].split(',').map(p => p.trim().replace(/^["']|["']$/g, ''));
          if (parts.length === 0 || (parts.length === 1 && !parts[0])) continue;
          const row: Record<string, string> = {};
          headers.forEach((h, idx) => {
            row[h] = parts[idx] || '';
          });
          rows.push(row);
        }
        setStagedRows(rows);
      }

      toast({
        title: "Migration Pre-flight Analysis Complete",
        description: `Identified ${data.source_system.toUpperCase()} schema. Validated ${data.valid_count} of ${data.total_rows} rows.`,
      });
    } catch (err: any) {
      toast({
        title: "Analysis Error",
        description: err?.message || "Failed to analyze legacy migration file.",
        variant: "destructive",
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCommitMigration = async () => {
    if (!stagedRows || stagedRows.length === 0) return;
    setIsProcessing(true);

    try {
      // Call Stage 2: Transactional Commit API
      const response = await apiClient.post<MigrationExecutionResult>("/migration/execute", {
        rows: stagedRows,
        source_system: selectedEhr === "auto" ? (analysisData?.source_system || "auto") : selectedEhr,
      });
      const data = (response as any)?.data || response;
      setExecutionResult(data);
      setAnalysisData(null);
      setStagedRows([]);
      toast({
        title: "Migration Completed",
        description: data.message || `Imported ${data.imported_patients} patients and ${data.imported_procedures} clinical procedures.`,
      });
    } catch (err: any) {
      toast({
        title: "Migration Failed",
        description: err?.message || "Failed to commit migration batch.",
        variant: "destructive",
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownloadTemplate = async (system: EhrSystem) => {
    try {
      const endpoint = system === "auto" ? "generic" : system;
      const response = await apiClient.get<any>(`/migration/templates/${endpoint}`);
      const content = typeof response === "string" ? response : (response as any)?.template_csv || (response as any)?.data || "";
      const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `template_${endpoint}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({
        title: "Template Downloaded",
        description: `Exported sample CSV template for ${endpoint.toUpperCase()}.`,
      });
    } catch {
      // Fallback manual template
      const fallbackHeaders = "first_name,last_name,date_of_birth,gender,email,phone,address_street,address_city,address_state,address_zip\nJohn,Doe,1990-05-15,male,john.doe@example.com,555-0199,123 Main St,Springfield,IL,62701";
      const blob = new Blob([fallbackHeaders], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `template_${system}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-8 max-w-5xl">
      <div>
        <h1 className="text-3xl font-bold">Legacy Migration Engine</h1>
        <p className="text-muted-foreground mt-1">
          Automated ETL pipeline for ingesting patient demographics, clinical procedures, and ledger records from Open Dental, Dentrix G4-G7, and Patterson Eaglesoft.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Source EHR Selection */}
        <Card className="border-slate-200 shadow-sm rounded-2xl md:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg font-bold">1. Select Source Dental System</CardTitle>
            <CardDescription>
              Choose your prior practice management software or let the intelligent ETL parser detect the schema.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {ehrOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setSelectedEhr(opt.id)}
                  className={`rounded-xl p-3 text-left border transition-all ${
                    selectedEhr === opt.id
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20"
                      : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <p className="text-sm font-bold flex items-center justify-between">
                    {opt.label}
                    {selectedEhr === opt.id && <Sparkles className="h-3.5 w-3.5 text-blue-600" />}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">{opt.sub}</p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* CSV Import */}
        <Card className="border-slate-200 shadow-sm rounded-2xl md:col-span-2">
          <CardHeader>
            <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-2">
              <Upload className="w-6 h-6" />
            </div>
            <CardTitle className="text-xl font-bold">2. Upload Export & Run Pre-flight Analysis</CardTitle>
            <CardDescription>
              Upload exported CSV/TSV from your legacy database. Stage 1 conducts non-destructive dry-run validation with duplicate detection and procedure fee reconciliation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:bg-slate-50 transition-colors">
              <input 
                type="file" 
                id="csv-upload" 
                className="hidden" 
                accept=".csv,.txt"
                onChange={handleFileUpload}
                disabled={isProcessing}
              />
              <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center">
                <Database className="w-10 h-10 text-slate-300 mb-3" />
                <span className="font-bold text-blue-600 hover:text-blue-700">Click to upload legacy database export</span>
                <span className="text-xs text-slate-500 mt-1">Accepts CSV or tab-delimited text exports</span>
              </label>
            </div>

            {isProcessing && (
              <div className="p-4 bg-blue-50 rounded-xl flex items-center gap-3">
                <Loader2 className="w-5 h-5 text-blue-600 animate-spin shrink-0" />
                <p className="text-sm font-bold text-blue-800">Transforming and validating legacy records...</p>
              </div>
            )}

            {executionResult && (
              <div className="p-5 bg-emerald-50 rounded-xl border border-emerald-200 space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
                  <div>
                    <p className="text-base font-bold text-emerald-900">Migration Successfully Committed</p>
                    <p className="text-xs text-emerald-700 font-medium">
                      All records ingested atomically under practice isolation.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Patients Ingested</p>
                    <p className="text-lg font-bold text-slate-800">{executionResult.imported_patients}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Historical Procedures</p>
                    <p className="text-lg font-bold text-blue-600">{executionResult.imported_procedures}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Appointments</p>
                    <p className="text-lg font-bold text-purple-600">{executionResult.imported_appointments}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Ledger Fees Ingested</p>
                    <p className="text-lg font-bold text-emerald-600">
                      {formatCurrency(executionResult.total_historical_procedure_fees || 0)}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {analysisData && (
              <div className="space-y-4 rounded-xl border border-slate-200 p-5 bg-slate-50/80">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-slate-800">Pre-Flight Validation Report</h3>
                      <Badge className="bg-blue-600 text-white font-mono text-[10px] uppercase">
                        {analysisData.source_system}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-500">Verify extracted demographics and clinical history before committing</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                      Valid: {analysisData.valid_count}
                    </Badge>
                    {analysisData.duplicate_count > 0 && (
                      <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                        Duplicates: {analysisData.duplicate_count}
                      </Badge>
                    )}
                    {analysisData.error_count > 0 && (
                      <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                        Errors: {analysisData.error_count}
                      </Badge>
                    )}
                  </div>
                </div>

                {analysisData.total_historical_procedure_fees !== undefined && analysisData.total_historical_procedure_fees > 0 && (
                  <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 flex items-center justify-between">
                    <span className="text-xs font-semibold text-purple-900">Total Historical Clinical Production Detected:</span>
                    <span className="text-sm font-bold text-purple-700">{formatCurrency(analysisData.total_historical_procedure_fees)}</span>
                  </div>
                )}

                {analysisData.preview && analysisData.preview.length > 0 && (
                  <div className="border rounded-lg bg-white overflow-hidden text-xs">
                    <div className="bg-slate-100 px-3 py-2 font-semibold text-slate-600 border-b flex justify-between">
                      <span>Transformed Patient Record Preview</span>
                      <span>Clinical History</span>
                    </div>
                    <div className="divide-y max-h-48 overflow-y-auto">
                      {analysisData.preview.map((p, idx) => (
                        <div key={idx} className="px-3 py-2.5 flex items-center justify-between">
                          <div>
                            <span className="font-semibold text-slate-800">{p.first_name} {p.last_name}</span>
                            <span className="text-slate-400 text-[11px] ml-2">DOB: {p.date_of_birth}</span>
                            <p className="text-slate-500 text-[11px]">{p.email || p.phone || "No contact"}</p>
                          </div>
                          <div className="text-right">
                            {p.historical_procedure_count ? (
                              <Badge variant="outline" className="text-[10px] bg-slate-50">
                                {p.historical_procedure_count} procs · {formatCurrency(p.total_procedure_fees || 0)}
                              </Badge>
                            ) : (
                              <span className="text-slate-400 text-[11px]">Demographics only</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData.errors && analysisData.errors.length > 0 && (
                  <div className="p-3 bg-red-50 rounded-lg border border-red-200 text-xs text-red-800 space-y-1">
                    <p className="font-bold flex items-center gap-1.5"><AlertTriangle className="h-4 w-4" /> Migration Warnings / Errors:</p>
                    <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                      {analysisData.errors.slice(0, 5).map((e, idx) => (
                        <li key={idx}>{e}</li>
                      ))}
                      {analysisData.errors.length > 5 && <li>...and {analysisData.errors.length - 5} more</li>}
                    </ul>
                  </div>
                )}

                {analysisData.valid_count > 0 && (
                  <Button 
                    onClick={handleCommitMigration} 
                    disabled={isProcessing}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold h-11"
                  >
                    <ArrowRight className="w-4 h-4 mr-2" />
                    Commit Transactional Migration ({analysisData.valid_count} Records)
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Export Templates */}
        <Card className="border-slate-200 shadow-sm rounded-2xl md:col-span-2">
          <CardHeader>
            <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-2">
              <FileDown className="w-6 h-6" />
            </div>
            <CardTitle className="text-xl font-bold">Standard Import & Export Templates</CardTitle>
            <CardDescription>
              Download pre-formatted CSV headers tailored for each dental software schema to test or format your migration.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <Button 
              variant="outline" 
              className="w-full justify-start h-12 font-semibold"
              onClick={() => handleDownloadTemplate("opendental")}
            >
              <FileSpreadsheet className="w-4 h-4 mr-2.5 text-blue-600" />
              Open Dental (.csv)
            </Button>
            <Button 
              variant="outline" 
              className="w-full justify-start h-12 font-semibold"
              onClick={() => handleDownloadTemplate("dentrix")}
            >
              <FileSpreadsheet className="w-4 h-4 mr-2.5 text-emerald-600" />
              Dentrix G4-G7 (.csv)
            </Button>
            <Button 
              variant="outline" 
              className="w-full justify-start h-12 font-semibold"
              onClick={() => handleDownloadTemplate("eaglesoft")}
            >
              <FileSpreadsheet className="w-4 h-4 mr-2.5 text-purple-600" />
              Eaglesoft (.csv)
            </Button>
            <Button 
              variant="outline" 
              className="w-full justify-start h-12 font-semibold"
              onClick={() => handleDownloadTemplate("generic")}
            >
              <FileSpreadsheet className="w-4 h-4 mr-2.5 text-slate-500" />
              CoreDent Schema (.csv)
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
