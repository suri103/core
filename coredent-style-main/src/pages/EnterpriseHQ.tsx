import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { format, subDays } from 'date-fns';
import {
  Activity,
  ArrowRightLeft,
  Award,
  Building2,
  CalendarRange,
  CircleDollarSign,
  Clock,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ApiResponse } from '@/types/api';
import {
  enterpriseApi,
  type DsoClinic,
  type DsoOverview,
  type DsoPatientSearchResult,
  type EnterpriseGroupAnalytics,
  type EnterprisePractice,
} from '@/services/enterpriseApi';
import { useToast } from '@/hooks/use-toast';

interface DateRange {
  start: string;
  end: string;
}

function unwrapResponse<T>(response: ApiResponse<T>): T {
  if (!response.success || response.data === undefined) {
    throw new Error(response.error?.message || 'The enterprise service is unavailable.');
  }
  return response.data;
}

function formatMetric(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatPeriod(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : format(date, 'MMM d, yyyy');
}

function MetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
}: {
  label: string;
  value: string;
  sublabel?: string;
  icon: typeof CircleDollarSign;
}) {
  return (
    <Card className="rounded-2xl border-slate-200 shadow-sm">
      <CardContent className="flex items-center gap-4 p-6">
        <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-black text-slate-900">{value}</p>
          {sublabel && <p className="text-xs text-slate-400 mt-0.5">{sublabel}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function EnterpriseHQ() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedClinicId, setSelectedClinicId] = useState<string>('');
  const [isSwitching, setIsSwitching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const dateRange = useMemo<DateRange>(() => {
    const end = new Date();
    return {
      start: format(subDays(end, 29), 'yyyy-MM-dd'),
      end: format(end, 'yyyy-MM-dd'),
    };
  }, []);

  const analyticsQuery = useQuery<EnterpriseGroupAnalytics>({
    queryKey: ['enterprise', 'group-analytics', dateRange.start, dateRange.end],
    queryFn: async () =>
      unwrapResponse(
        await enterpriseApi.getGroupAnalytics({
          start_date: dateRange.start,
          end_date: dateRange.end,
        }),
      ),
    staleTime: 60_000,
  });

  const practicesQuery = useQuery<EnterprisePractice[]>({
    queryKey: ['enterprise', 'group-practices'],
    queryFn: async () => unwrapResponse(await enterpriseApi.listGroupPractices({ page: 1, limit: 100 })),
    staleTime: 5 * 60_000,
  });

  const dsoOverviewQuery = useQuery<DsoOverview>({
    queryKey: ['enterprise', 'dso-overview'],
    queryFn: async () => unwrapResponse(await enterpriseApi.getDsoOverview()),
    staleTime: 60_000,
    retry: false,
  });

  const clinicsQuery = useQuery<DsoClinic[]>({
    queryKey: ['enterprise', 'dso-clinics'],
    queryFn: async () => unwrapResponse(await enterpriseApi.getDsoClinics()),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const searchPatientQuery = useQuery<DsoPatientSearchResult[]>({
    queryKey: ['enterprise', 'dso-patient-search', searchQuery],
    queryFn: async () => unwrapResponse(await enterpriseApi.searchDsoPatients(searchQuery.trim())),
    enabled: searchQuery.trim().length >= 2,
    staleTime: 30_000,
  });

  const handleSwitchContext = async (clinicId: string) => {
    if (!clinicId) return;
    setIsSwitching(true);
    try {
      const res = unwrapResponse(await enterpriseApi.switchContext(clinicId));
      if (res.access_token) {
        localStorage.setItem('access_token', res.access_token);
      }
      setSelectedClinicId(clinicId);
      toast({
        title: 'Clinic Context Switched',
        description: `Active tenant switched to ${res.active_practice_name}.`,
      });
      void queryClient.invalidateQueries();
    } catch (err: any) {
      toast({
        title: 'Switch Failed',
        description: err?.message || 'Failed to switch clinic context.',
        variant: 'destructive',
      });
    } finally {
      setIsSwitching(false);
    }
  };

  const analytics = analyticsQuery.data;
  const dsoOverview = dsoOverviewQuery.data;
  const clinics = clinicsQuery.data ?? [];
  const practicesById = new Map(
    (practicesQuery.data ?? []).map((practice) => [practice.id, practice]),
  );
  const locations = analytics?.by_location ?? [];
  const periodLabel = analytics
    ? `${formatPeriod(analytics.period.start)} – ${formatPeriod(analytics.period.end)}`
    : `${dateRange.start} – ${dateRange.end}`;

  const arAging = dsoOverview?.ar_aging ?? {
    current_30: 0,
    days_31_60: 0,
    days_61_90: 0,
    over_90: 0,
  };
  const totalAr = (arAging.current_30 + arAging.days_31_60 + arAging.days_61_90 + arAging.over_90) || 1;

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-10">
      {/* Header with Context Switcher */}
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <Building2 className="h-8 w-8 text-indigo-600" aria-hidden="true" />
            <h1 className="text-3xl font-black text-slate-900">Enterprise HQ</h1>
            <Badge variant="secondary">Group scope</Badge>
          </div>
          <p className="mt-2 flex items-center gap-2 text-sm text-slate-500">
            <CalendarRange className="h-4 w-4" aria-hidden="true" />
            Authorized group analytics for {periodLabel}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {clinics.length > 0 && (
            <div className="flex items-center gap-2">
              <Select
                value={selectedClinicId}
                onValueChange={(val) => {
                  setSelectedClinicId(val);
                  void handleSwitchContext(val);
                }}
                disabled={isSwitching}
              >
                <SelectTrigger className="w-[220px] bg-white border-slate-300">
                  <ArrowRightLeft className="h-3.5 w-3.5 mr-2 text-indigo-600" />
                  <SelectValue placeholder="Switch Clinic Context" />
                </SelectTrigger>
                <SelectContent className="max-h-60 overflow-y-auto">
                  {clinics.length === 0 ? (
                    <div className="py-2 px-3 text-center text-xs text-muted-foreground">
                      No locations found
                    </div>
                  ) : (
                    clinics.map((clinic) => (
                      <SelectItem key={clinic.id} value={clinic.id}>
                        {clinic.name} ({clinic.city || 'Clinic'})
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
          )}

          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => {
              void analyticsQuery.refetch();
              void practicesQuery.refetch();
              void dsoOverviewQuery.refetch();
            }}
            disabled={analyticsQuery.isFetching || practicesQuery.isFetching || dsoOverviewQuery.isFetching}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${analyticsQuery.isFetching || practicesQuery.isFetching || dsoOverviewQuery.isFetching ? 'animate-spin' : ''}`}
              aria-hidden="true"
            />
            Refresh data
          </Button>
        </div>
      </div>

      {analyticsQuery.isLoading && (
        <Card>
          <CardContent className="p-8 text-center text-slate-500">Loading live group analytics…</CardContent>
        </Card>
      )}

      {analyticsQuery.isError && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 p-6 text-amber-950">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-bold">Group analytics unavailable</p>
              <p className="mt-1 text-sm">
                The server did not authorize or return enterprise data. No practice-level or sample numbers are shown.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {analytics && (
        <>
          {/* Consolidated Group KPIs */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Group production" value={formatMetric(analytics.consolidated.production)} icon={CircleDollarSign} />
            <MetricCard label="Group collections" value={formatMetric(analytics.consolidated.collections)} icon={CircleDollarSign} />
            <MetricCard label="New patients" value={formatMetric(analytics.consolidated.new_patients)} icon={Users} />
            <MetricCard label="Average utilization" value={`${formatMetric(analytics.consolidated.avg_utilization)}%`} icon={Activity} />
          </div>

          {/* AR Aging Breakdown & Financial Performance */}
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="rounded-2xl border-slate-200 shadow-sm lg:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-indigo-600" />
                    <CardTitle className="text-lg">Accounts Receivable (AR) Aging Breakdown</CardTitle>
                  </div>
                  {dsoOverview && (
                    <Badge variant="outline" className="text-xs bg-indigo-50 text-indigo-700 border-indigo-200">
                      Collection Rate: {dsoOverview.financials.collection_rate.toFixed(1)}%
                    </Badge>
                  )}
                </div>
                <CardDescription>Consolidated outstanding patient and insurance receivables across all affiliated locations</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="rounded-xl border p-3 bg-emerald-50/40 border-emerald-100">
                    <p className="text-[11px] font-bold uppercase text-emerald-800">Current (0-30 d)</p>
                    <p className="text-lg font-black text-emerald-700 mt-1">{formatCurrency(arAging.current_30)}</p>
                    <Progress value={(arAging.current_30 / totalAr) * 100} className="h-1.5 mt-2 bg-emerald-100" />
                  </div>
                  <div className="rounded-xl border p-3 bg-blue-50/40 border-blue-100">
                    <p className="text-[11px] font-bold uppercase text-blue-800">31-60 Days</p>
                    <p className="text-lg font-black text-blue-700 mt-1">{formatCurrency(arAging.days_31_60)}</p>
                    <Progress value={(arAging.days_31_60 / totalAr) * 100} className="h-1.5 mt-2 bg-blue-100" />
                  </div>
                  <div className="rounded-xl border p-3 bg-amber-50/40 border-amber-100">
                    <p className="text-[11px] font-bold uppercase text-amber-800">61-90 Days</p>
                    <p className="text-lg font-black text-amber-700 mt-1">{formatCurrency(arAging.days_61_90)}</p>
                    <Progress value={(arAging.days_61_90 / totalAr) * 100} className="h-1.5 mt-2 bg-amber-100" />
                  </div>
                  <div className="rounded-xl border p-3 bg-red-50/40 border-red-100">
                    <p className="text-[11px] font-bold uppercase text-red-800">Over 90 Days</p>
                    <p className="text-lg font-black text-red-700 mt-1">{formatCurrency(arAging.over_90)}</p>
                    <Progress value={(arAging.over_90 / totalAr) * 100} className="h-1.5 mt-2 bg-red-100" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Provider Productivity Leaderboard */}
            <Card className="rounded-2xl border-slate-200 shadow-sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-amber-500" />
                  <CardTitle className="text-lg">Top Provider Productivity</CardTitle>
                </div>
                <CardDescription>Completed patient visits across group</CardDescription>
              </CardHeader>
              <CardContent>
                {dsoOverview?.provider_leaderboard && dsoOverview.provider_leaderboard.length > 0 ? (
                  <div className="space-y-3">
                    {dsoOverview.provider_leaderboard.slice(0, 4).map((p, idx) => (
                      <div key={p.provider_id} className="flex items-center justify-between text-xs rounded-lg border p-2.5 bg-slate-50/50">
                        <div className="flex items-center gap-2.5">
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                            idx === 0 ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-700'
                          }`}>
                            {idx + 1}
                          </span>
                          <div>
                            <p className="font-semibold text-slate-800">{p.provider_name}</p>
                            <p className="text-[10px] text-slate-500">Clinic: {p.clinic_name}</p>
                          </div>
                        </div>
                        <Badge variant="secondary" className="font-mono text-[10px]">
                          {p.completed_appointments} visits
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-4 text-center">No provider rankings recorded.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Cross-Clinic Master Patient Search */}
          <Card className="rounded-2xl border-slate-200 shadow-sm">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Search className="h-5 w-5 text-indigo-600" />
                <CardTitle className="text-lg">DSO Master Patient Directory Search</CardTitle>
              </div>
              <CardDescription>Instantly locate patient records across all group practices and clinics without context switching</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search by patient name, email, or phone across clinics..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-10 rounded-xl"
                />
              </div>

              {searchPatientQuery.isFetching && (
                <p className="text-xs text-slate-500">Searching master DSO index...</p>
              )}

              {searchPatientQuery.data && searchPatientQuery.data.length > 0 && (
                <div className="rounded-xl border overflow-hidden text-xs">
                  <div className="bg-slate-100 px-3 py-2 font-semibold text-slate-600 border-b flex justify-between">
                    <span>Patient</span>
                    <span>Home Practice / Location</span>
                  </div>
                  <div className="divide-y max-h-48 overflow-y-auto">
                    {searchPatientQuery.data.map((p) => (
                      <div key={p.id} className="px-3 py-2.5 flex items-center justify-between hover:bg-slate-50">
                        <div>
                          <p className="font-semibold text-slate-900">{p.first_name} {p.last_name}</p>
                          <p className="text-[11px] text-slate-500">{p.email || p.phone || 'No direct contact'} {p.date_of_birth ? `· DOB: ${p.date_of_birth}` : ''}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[11px] bg-indigo-50/50 text-indigo-700 border-indigo-200">
                            <MapPin className="h-3 w-3 mr-1 inline" />
                            {p.practice_name} ({p.practice_city || 'HQ'})
                          </Badge>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs text-indigo-600 hover:text-indigo-800"
                            onClick={() => handleSwitchContext(p.practice_id)}
                          >
                            Switch to Clinic
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {searchQuery.trim().length >= 2 && !searchPatientQuery.isFetching && searchPatientQuery.data?.length === 0 && (
                <p className="text-xs text-slate-400 italic">No patients found matching &quot;{searchQuery}&quot; across any affiliated clinic.</p>
              )}
            </CardContent>
          </Card>

          {/* Location Performance Table */}
          <Card className="rounded-2xl border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-indigo-600" aria-hidden="true" />
                Location performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              {locations.length === 0 ? (
                <p className="text-sm text-slate-500">No location data is available for this period.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-left text-sm">
                    <thead className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-3 py-3 font-bold">Location</th>
                        <th className="px-3 py-3 text-right font-bold">Production</th>
                        <th className="px-3 py-3 text-right font-bold">Collections</th>
                        <th className="px-3 py-3 text-right font-bold">New patients</th>
                        <th className="px-3 py-3 text-right font-bold">Utilization</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {locations.map((location) => {
                        const practice = practicesById.get(location.practice_id);
                        return (
                          <tr key={location.practice_id} className="text-slate-700">
                            <td className="px-3 py-4">
                              <p className="font-semibold text-slate-900">{location.practice_name}</p>
                              {practice?.address_city || practice?.address_state ? (
                                <p className="mt-1 text-xs text-slate-500">
                                  {[practice.address_city, practice.address_state].filter(Boolean).join(', ')}
                                </p>
                              ) : null}
                            </td>
                            <td className="px-3 py-4 text-right font-medium">{formatMetric(location.production)}</td>
                            <td className="px-3 py-4 text-right font-medium">{formatMetric(location.collections)}</td>
                            <td className="px-3 py-4 text-right font-medium">{formatMetric(location.new_patients)}</td>
                            <td className="px-3 py-4 text-right font-medium">{formatMetric(location.utilization)}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {practicesQuery.isError && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 p-6 text-amber-950">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-bold">Location directory unavailable</p>
              <p className="mt-1 text-sm">Analytics remain visible, but location address details could not be loaded.</p>
            </div>
          </CardContent>
        </Card>
      )}

      {!analyticsQuery.isLoading && !analyticsQuery.isError && !analytics && (
        <Card>
          <CardContent className="p-8 text-center text-slate-500">No group analytics were returned.</CardContent>
        </Card>
      )}
    </div>
  );
}
