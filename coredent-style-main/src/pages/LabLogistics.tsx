import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Beaker, ExternalLink, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { labsApi, type LabCaseRecord } from '@/services/labsApi';

function caseLabel(labCase: LabCaseRecord): string { return labCase.case_number ?? `Case ${labCase.id.slice(0, 8)}`; }

export default function LabLogistics() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['lab-cases'], queryFn: () => labsApi.listCases() });
  const cases = query.data?.cases ?? [];
  const selected = cases.find((labCase) => labCase.id === selectedId) ?? cases[0];

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-10">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-center"><div><div className="flex items-center gap-3"><Beaker className="h-8 w-8 text-indigo-600" /><h1 className="text-3xl font-black text-slate-900">Lab Cases</h1></div><p className="mt-2 text-sm text-slate-500">Live lab cases from the practice database.</p></div><Button asChild className="rounded-xl"><Link to="/labs">Open lab management</Link></Button></div>
      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><CardTitle>Cases {query.data && <span className="text-sm font-normal text-slate-500">({query.data.count})</span>}</CardTitle></CardHeader><CardContent>{query.isLoading && <p className="text-sm text-slate-500">Loading lab cases…</p>}{query.isError && <p className="text-sm text-red-600">Unable to load lab cases.</p>}{!query.isLoading && !query.isError && cases.length === 0 && <p className="py-6 text-sm text-slate-500">No live lab cases found.</p>}{cases.length > 0 && <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.7fr)]"><div className="divide-y divide-slate-100">{cases.map((labCase) => <button key={labCase.id} type="button" onClick={() => setSelectedId(labCase.id)} className={`flex w-full items-center justify-between gap-4 py-4 text-left ${selected?.id === labCase.id ? 'rounded-lg bg-indigo-50 px-3' : ''}`}><div><p className="font-bold text-slate-900">{caseLabel(labCase)}</p><p className="text-sm text-slate-500">{labCase.case_type ?? 'Lab case'} · Patient {labCase.patient_id?.slice(0, 8) ?? 'unknown'}</p><p className="text-xs text-slate-400">Due {labCase.due_date ? new Date(labCase.due_date).toLocaleDateString() : 'not set'}</p></div><Badge variant="secondary">{labCase.status ?? 'unknown'}</Badge></button>)}</div>{selected && <Card className="h-fit bg-slate-50"><CardHeader><CardTitle>{caseLabel(selected)}</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><p><strong>Status:</strong> {selected.status ?? 'unknown'}</p><p><strong>Lab:</strong> {selected.lab_id ?? 'not assigned'}</p><p><strong>Tracking:</strong> {selected.tracking_number ?? 'not available'}</p><p><strong>Notes:</strong> {selected.lab_notes ?? selected.provider_notes ?? 'No notes'}</p><Button asChild variant="outline" className="w-full rounded-lg"><Link to="/labs"><ExternalLink className="mr-2 h-4 w-4" />Manage case</Link></Button></CardContent></Card>}</div>}</CardContent></Card>
      <Card className="border-amber-200 bg-amber-50"><CardContent className="flex items-start gap-3 p-6 text-amber-950"><ShieldAlert className="mt-0.5 h-5 w-5" /><p className="text-sm">Courier tracking, lab messaging, photo uploads, and automatic milestones require provider integrations. The dashboard now shows only persisted case data.</p></CardContent></Card>
    </div>
  );
}