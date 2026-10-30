import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRightLeft, Search, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { referralsApi, type ReferralRecord } from '@/services/referralsApi';

function patientLabel(referral: ReferralRecord): string {
  const patient = referral.patient;
  if (patient?.first_name || patient?.last_name) return `${patient.first_name ?? ''} ${patient.last_name ?? ''}`.trim();
  return referral.patient_id ? `Patient ${referral.patient_id.slice(0, 8)}` : 'Unassigned patient';
}

export default function ReferralHub() {
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['referrals'], queryFn: () => referralsApi.list() });
  const referrals = useMemo(() => (query.data?.referrals ?? []).filter((referral) => `${patientLabel(referral)} ${referral.referral_type ?? ''} ${referral.status ?? ''}`.toLowerCase().includes(search.toLowerCase())), [query.data?.referrals, search]);

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-10">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-center"><div><div className="flex items-center gap-3"><ArrowRightLeft className="h-8 w-8 text-blue-600" /><h1 className="text-3xl font-black text-slate-900">Referral Management</h1></div><p className="mt-2 text-sm text-slate-500">Live referrals scoped to the current practice.</p></div><Button asChild className="rounded-xl"><Link to="/referrals">Open referral management</Link></Button></div>
      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between"><CardTitle>Referral queue {query.data && <span className="text-sm font-normal text-slate-500">({query.data.count})</span>}</CardTitle><div className="relative w-full md:max-w-sm"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input aria-label="Search referrals" className="h-10 w-full rounded-lg border border-slate-300 pl-9 pr-3 text-sm" placeholder="Search patient, type, status" value={search} onChange={(event) => setSearch(event.target.value)} /></div></CardHeader><CardContent>{query.isLoading && <p className="text-sm text-slate-500">Loading referrals…</p>}{query.isError && <p className="text-sm text-red-600">Unable to load referrals.</p>}{!query.isLoading && !query.isError && referrals.length === 0 && <p className="py-6 text-sm text-slate-500">No live referrals match this search.</p>}{referrals.length > 0 && <div className="divide-y divide-slate-100">{referrals.map((referral) => <div key={referral.id} className="flex flex-col gap-3 py-5 md:flex-row md:items-center md:justify-between"><div><p className="font-bold text-slate-900">{patientLabel(referral)}</p><p className="text-sm text-slate-500">{referral.referral_type ?? 'Referral'}{referral.referral_date ? ` · ${new Date(referral.referral_date).toLocaleDateString()}` : ''}</p>{(referral.notes || referral.reason) && <p className="mt-1 text-sm text-slate-600">{referral.notes ?? referral.reason}</p>}</div><Badge variant="secondary">{referral.status ?? 'unknown'}</Badge></div>)}</div>}</CardContent></Card>
      <Card className="border-amber-200 bg-amber-50"><CardContent className="flex items-start gap-3 p-6 text-amber-950"><ShieldAlert className="mt-0.5 h-5 w-5" /><p className="text-sm">Cross-location smart matching is not implemented. This page does not invent availability or referral counts; multi-location routing requires a group directory and scheduling API.</p></CardContent></Card>
    </div>
  );
}