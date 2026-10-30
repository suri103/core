// ============================================
// CoreDent PMS - Patient Self-Service Portal
// Public-facing portal for patients to view
// appointments, bills, treatment plans & pay online
// ============================================

import { useState, useEffect, useCallback } from 'react';
import {
  Calendar,
  CreditCard,
  FileText,
  Heart,
  Shield,
  Clock,
  CheckCircle2,
  AlertCircle,
  LogOut,
  User,
  DollarSign,
  Stethoscope,
  ChevronRight,
  Loader2,
  Lock,
  Sparkles,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { SignaturePad } from '@/components/ui/signature-pad';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { getCaptchaToken } from '@/lib/recaptcha';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface PortalSession {
  access_token: string;
  patient_name: string;
  practice_name: string;
  expires_at: string;
}

interface Appointment {
  id: string;
  start_time: string | null;
  end_time: string | null;
  status: string;
  reason: string | null;
  notes: string | null;
  provider_name: string | null;
}

interface InvoiceItem {
  id: string;
  invoice_number: string;
  date: string | null;
  total_amount: number;
  amount_paid: number;
  balance_due: number;
  status: string;
  description: string | null;
}

interface TreatmentPlanItem {
  id: string;
  plan_name: string;
  status: string;
  total_estimated_cost: number;
  total_insurance_estimate: number;
  total_patient_responsibility: number;
  created_date: string | null;
  diagnosis: string | null;
  treatment_goals: string | null;
}

interface InsurancePolicy {
  id: string;
  insurance_type: string;
  subscriber_id: string;
  group_number: string | null;
  effective_date: string | null;
  annual_maximum: number;
  annual_deductible: number;
  deductible_met: number;
  preventive_coverage: number;
  basic_coverage: number;
  major_coverage: number;
}

// ── Login Screen ─────────────────────────────────────────────────────

function PortalLogin({ onLogin }: { onLogin: (session: PortalSession) => void }) {
  const [email, setEmail] = useState('');
  const [dob, setDob] = useState('');
  const [practiceSlug, setPracticeSlug] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // Option A inbox proof: step 1 sends a magic link, step 2 consumes its code.
  const [linkSent, setLinkSent] = useState(false);
  const [code, setCode] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      let captchaToken: string | undefined;
      if (import.meta.env.VITE_RECAPTCHA_SITE_KEY?.trim()) {
        captchaToken = await getCaptchaToken('portal_access');
      }

      const res = await fetch(
        `${API_BASE}/portal/access`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            date_of_birth: dob,
            practice_slug: practiceSlug,
            captcha_token: captchaToken,
          }),
        }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Verification failed');
      }
      setLinkSent(true);
      setResendCooldown(60);
      const interval = setInterval(() => {
        setResendCooldown((c) => {
          if (c <= 1) clearInterval(interval);
          return c - 1;
        });
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Unable to verify. Please contact your dental office.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setLoading(true);
    setError('');
    try {
      let captchaToken: string | undefined;
      if (import.meta.env.VITE_RECAPTCHA_SITE_KEY?.trim()) {
        captchaToken = await getCaptchaToken('portal_access');
      }
      const res = await fetch(`${API_BASE}/portal/access/resend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          date_of_birth: dob,
          practice_slug: practiceSlug,
          captcha_token: captchaToken,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Unable to resend. Please try again later.');
      }
      setResendCooldown(60);
      const interval = setInterval(() => {
        setResendCooldown((c) => {
          if (c <= 1) clearInterval(interval);
          return c - 1;
        });
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Unable to resend. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_BASE}/portal/access/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code.trim() }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'This sign-in link is invalid or expired.');
      }
      const session: PortalSession = await res.json();
      onLogin(session);
    } catch (err: any) {
      setError(err.message || 'This sign-in link is invalid or expired.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center mx-auto mb-6 shadow-2xl shadow-blue-200">
            <Stethoscope className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Patient Portal</h1>
          <p className="text-slate-500 font-medium mt-2">View appointments, bills & pay online</p>
        </div>

        <Card className="border-none shadow-[0_30px_80px_rgba(0,0,0,0.08)] rounded-[2rem] overflow-hidden">
          <CardContent className="p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Practice Code</Label>
                <Input
                  value={practiceSlug}
                  onChange={(e) => setPracticeSlug(e.target.value)}
                  placeholder="e.g. bright-smiles-dental"
                  className="h-12 rounded-xl border-slate-200 font-medium"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Email Address</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="h-12 rounded-xl border-slate-200 font-medium"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Date of Birth</Label>
                <Input
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  className="h-12 rounded-xl border-slate-200 font-medium"
                  required
                />
              </div>

              {error && (
                <div className="p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm font-bold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}

              {linkSent && (
                <div className="p-4 rounded-xl bg-blue-50 border border-blue-100 text-blue-700 text-sm font-bold">
                  Check your email for a sign-in link. It expires in 15 minutes and can be used once.
                </div>
              )}

              <Button
                type="submit"
                disabled={loading || linkSent}
                className="w-full h-14 rounded-2xl font-black text-base bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-xl shadow-blue-200 transition-all hover:scale-[1.02] active:scale-95"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Lock className="w-5 h-5 mr-2" />
                )}
                {loading ? 'Verifying...' : 'Email Me a Sign-In Link'}
              </Button>

              {linkSent && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleResend}
                  disabled={loading || resendCooldown > 0}
                  className="w-full"
                >
                  {resendCooldown > 0
                    ? `Resend available in ${resendCooldown}s`
                    : loading
                      ? 'Resending...'
                      : 'Resend Sign-In Link'}
                </Button>
              )}

              {linkSent && (
                <div className="space-y-2 pt-2">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Sign-In Code</Label>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="Paste the code from your email link"
                    className="h-12 rounded-xl border-slate-200 font-medium"
                  />
                  <Button
                    type="button"
                    disabled={loading || !code.trim()}
                    onClick={(e) => void handleVerifyCode(e as unknown as React.FormEvent)}
                    className="w-full h-12 rounded-2xl font-black text-base"
                    variant="outline"
                  >
                    {loading ? 'Signing in...' : 'Sign In With Code'}
                  </Button>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2 text-slate-400 justify-center">
                <Shield className="w-4 h-4" />
                <span className="text-xs font-bold">HIPAA-Compliant • Encrypted Connection</span>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

interface DocumentItem {
  id: string;
  name: string;
  type: string;
  is_completed: boolean;
  content: string | null;
  assigned_date: string | null;
  completed_date: string | null;
}

// ── Portal Dashboard ─────────────────────────────────────────────────

function PortalDashboard({ session, onLogout }: { session: PortalSession; onLogout: () => void }) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [totalOutstanding, setTotalOutstanding] = useState(0);
  const [treatmentPlans, setTreatmentPlans] = useState<TreatmentPlanItem[]>([]);
  const [insurance, setInsurance] = useState<InsurancePolicy[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);

  const [signingDoc, setSigningDoc] = useState<DocumentItem | null>(null);
  const [signatureData, setSignatureData] = useState("");
  const [signerName, setSignerName] = useState("");
  const [signatureError, setSignatureError] = useState("");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [isSubmittingSignature, setIsSubmittingSignature] = useState(false);

  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [payingInvoice, setPayingInvoice] = useState<InvoiceItem | null>(null);
  const [paymentAmount, setPaymentAmount] = useState<string>("");

  const useTypedSignature = () => {
    const normalizedName = signerName.trim();
    if (!normalizedName) {
      setSignatureError('Enter your full legal name before using a typed signature.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = 500;
    canvas.height = 200;
    const context = canvas.getContext('2d');
    if (!context) {
      setSignatureError('Typed signatures are not supported by this browser.');
      return;
    }

    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#111827';
    context.font = 'italic 42px serif';
    context.fillText(normalizedName, 24, 112, 452);
    setSignatureData(canvas.toDataURL('image/png'));
    setSignatureError('');
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setFetchError(false);
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    };

    try {
      const [aptRes, billRes, txRes, insRes, docRes] = await Promise.allSettled([
        fetch(`${API_BASE}/portal/appointments`, { headers }),
        fetch(`${API_BASE}/portal/billing`, { headers }),
        fetch(`${API_BASE}/portal/treatment-plans`, { headers }),
        fetch(`${API_BASE}/portal/insurance`, { headers }),
        fetch(`${API_BASE}/portal/documents`, { headers }),
      ]);

      // An expired/invalid portal session must re-authenticate, not render an
      // empty "$0 outstanding" dashboard.
      const results = [aptRes, billRes, txRes, insRes, docRes];
      const unauthorized = results.some(
        (res) =>
          res.status === 'fulfilled' &&
          (res.value.status === 401 || res.value.status === 403),
      );
      if (unauthorized) {
        onLogout();
        return;
      }

      let anySucceeded = false;
      if (aptRes.status === 'fulfilled' && aptRes.value.ok) {
        const d = await aptRes.value.json();
        setAppointments(d.appointments || []);
        anySucceeded = true;
      }
      if (billRes.status === 'fulfilled' && billRes.value.ok) {
        const d = await billRes.value.json();
        setInvoices(d.invoices || []);
        setTotalOutstanding(d.total_outstanding || 0);
        anySucceeded = true;
      }
      if (txRes.status === 'fulfilled' && txRes.value.ok) {
        const d = await txRes.value.json();
        setTreatmentPlans(d.treatment_plans || []);
        anySucceeded = true;
      }
      if (insRes.status === 'fulfilled' && insRes.value.ok) {
        const d = await insRes.value.json();
        setInsurance(d.insurance_policies || []);
        anySucceeded = true;
      }
      if (docRes.status === 'fulfilled' && docRes.value.ok) {
        const d = await docRes.value.json();
        setDocuments(d.documents || []);
        anySucceeded = true;
      }

      // Distinguish "no data" from "could not load": when every feed failed
      // show an error state instead of a healthy-looking empty portal.
      setFetchError(!anySucceeded);
    } catch {
      setFetchError(true);
    } finally {
      setLoading(false);
    }
  }, [session.access_token, onLogout]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  };
  const formatTime = (iso: string | null) => {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };
  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/portal/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
    } finally {
      onLogout();
    }
  };


  const statusColor = (s: string) => {
    const lower = s.toLowerCase();
    if (['paid', 'completed', 'accepted'].includes(lower)) return 'bg-emerald-50 text-emerald-600 border-emerald-100';
    if (['overdue', 'denied', 'cancelled'].includes(lower)) return 'bg-red-50 text-red-600 border-red-100';
    if (['pending', 'draft', 'scheduled'].includes(lower)) return 'bg-amber-50 text-amber-600 border-amber-100';
    return 'bg-blue-50 text-blue-600 border-blue-100';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto" />
          <p className="font-bold text-slate-500">Loading your health data...</p>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4">
        <Card className="border-none shadow-[0_30px_80px_rgba(0,0,0,0.08)] rounded-[2rem]">
          <CardContent className="p-8 max-w-md text-center space-y-4">
            <AlertCircle className="w-12 h-12 mx-auto text-red-400" />
            <h2 className="text-xl font-black text-slate-800">Could not load your portal</h2>
            <p className="text-sm text-slate-500 font-medium">
              We were unable to reach the practice to load your appointments and bills. This is not
              an empty account — the data simply failed to load.
            </p>
            <div className="flex gap-3 justify-center pt-2">
              <Button onClick={fetchData} className="rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white">
                <Loader2 className="w-4 h-4 mr-2" /> Try Again
              </Button>
              <Button variant="outline" onClick={handleLogout} className="rounded-xl font-bold">
                Sign Out
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/30">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-slate-100 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-100">
              <Stethoscope className="w-5 h-5" />
            </div>
            <div>
              <p className="font-black text-slate-900 tracking-tight">{session.practice_name}</p>
              <p className="text-xs font-bold text-slate-400">Patient Portal</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-50">
              <User className="w-4 h-4 text-slate-500" />
              <span className="font-bold text-sm text-slate-700">{session.patient_name}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="rounded-xl text-slate-400 hover:text-red-500">
              <LogOut className="w-4 h-4 mr-1" /> Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        {/* Welcome + Quick Stats */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">
              Welcome back, {session.patient_name.split(' ')[0]} <Sparkles className="w-7 h-7 inline text-amber-400" />
            </h1>
            <p className="text-slate-500 font-medium mt-1">Here's your dental health overview</p>
          </div>
        </div>

        {/* Quick Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.04)] rounded-[1.5rem] group hover:shadow-[0_20px_50px_rgba(0,0,0,0.06)] transition-all">
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2.5 rounded-xl bg-blue-50"><Calendar className="w-5 h-5 text-blue-600" /></div>
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Upcoming</span>
              </div>
              <p className="text-2xl font-black text-slate-900">{appointments.length}</p>
              <p className="text-xs text-slate-400 font-bold mt-1">Appointments</p>
            </CardContent>
          </Card>
          <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.04)] rounded-[1.5rem] group hover:shadow-[0_20px_50px_rgba(0,0,0,0.06)] transition-all">
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2.5 rounded-xl bg-amber-50"><DollarSign className="w-5 h-5 text-amber-600" /></div>
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Balance</span>
              </div>
              <p className="text-2xl font-black text-slate-900">${totalOutstanding.toLocaleString()}</p>
              <p className="text-xs text-slate-400 font-bold mt-1">Outstanding</p>
            </CardContent>
          </Card>
          <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.04)] rounded-[1.5rem] group hover:shadow-[0_20px_50px_rgba(0,0,0,0.06)] transition-all">
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2.5 rounded-xl bg-emerald-50"><FileText className="w-5 h-5 text-emerald-600" /></div>
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Plans</span>
              </div>
              <p className="text-2xl font-black text-slate-900">{treatmentPlans.length}</p>
              <p className="text-xs text-slate-400 font-bold mt-1">Treatment Plans</p>
            </CardContent>
          </Card>
          <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.04)] rounded-[1.5rem] group hover:shadow-[0_20px_50px_rgba(0,0,0,0.06)] transition-all">
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2.5 rounded-xl bg-purple-50"><Shield className="w-5 h-5 text-purple-600" /></div>
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Insurance</span>
              </div>
              <p className="text-2xl font-black text-slate-900">{insurance.length}</p>
              <p className="text-xs text-slate-400 font-bold mt-1">Active Policies</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Tabbed Content */}
        <Tabs defaultValue="appointments" className="w-full">
          <Card className="border-none shadow-[0_20px_60px_rgba(0,0,0,0.04)] rounded-[2rem] overflow-hidden">
            <TabsList className="h-14 bg-slate-50/50 p-1.5 gap-1.5 border-b border-slate-100 w-full justify-start px-6 rounded-none flex-wrap h-auto">
              <TabsTrigger value="appointments" className="rounded-lg px-5 py-2 font-bold text-slate-500 data-[state=active]:bg-white data-[state=active]:text-blue-600 data-[state=active]:shadow-sm">
                <Calendar className="w-4 h-4 mr-2" /> Appointments
              </TabsTrigger>
              <TabsTrigger value="billing" className="rounded-lg px-5 py-2 font-bold text-slate-500 data-[state=active]:bg-white data-[state=active]:text-blue-600 data-[state=active]:shadow-sm">
                <CreditCard className="w-4 h-4 mr-2" /> Billing
              </TabsTrigger>
              <TabsTrigger value="treatments" className="rounded-lg px-5 py-2 font-bold text-slate-500 data-[state=active]:bg-white data-[state=active]:text-blue-600 data-[state=active]:shadow-sm">
                <Heart className="w-4 h-4 mr-2" /> Treatment
              </TabsTrigger>
              <TabsTrigger value="insurance" className="rounded-lg px-5 py-2 font-bold text-slate-500 data-[state=active]:bg-white data-[state=active]:text-blue-600 data-[state=active]:shadow-sm">
                <Shield className="w-4 h-4 mr-2" /> Insurance
              </TabsTrigger>
              <TabsTrigger value="forms" className="rounded-lg px-5 py-2 font-bold text-slate-500 data-[state=active]:bg-white data-[state=active]:text-blue-600 data-[state=active]:shadow-sm">
                <FileText className="w-4 h-4 mr-2" /> Digital Forms
              </TabsTrigger>
            </TabsList>

            {/* Appointments Tab */}
            <TabsContent value="appointments" className="p-8 m-0 space-y-4">
              <h3 className="text-lg font-black text-slate-800 tracking-tight">Upcoming Appointments</h3>
              {appointments.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                  <Calendar className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p className="font-bold">No upcoming appointments.</p>
                  <p className="text-sm mt-1">Call the office or use online booking to schedule.</p>
                </div>
              ) : (
                appointments.map((apt) => (
                  <div key={apt.id} className="flex items-center justify-between p-5 rounded-2xl border border-slate-100 hover:bg-blue-50/30 transition-colors group">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 group-hover:bg-blue-100 transition-colors">
                        <Clock className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="font-black text-slate-900">{formatDate(apt.start_time)}</p>
                        <p className="text-sm text-slate-500 font-medium">{formatTime(apt.start_time)} — {apt.reason || 'General Visit'}</p>
                        {apt.provider_name && <p className="text-xs text-slate-400 font-bold mt-0.5">Dr. {apt.provider_name}</p>}
                      </div>
                    </div>
                    <Badge variant="outline" className={cn("font-bold uppercase tracking-wider text-[9px] px-3 py-1", statusColor(apt.status))}>
                      {apt.status}
                    </Badge>
                  </div>
                ))
              )}
            </TabsContent>

            {/* Billing Tab */}
            <TabsContent value="billing" className="p-8 m-0 space-y-6">
              {totalOutstanding > 0 && (
                <div className="p-6 rounded-2xl bg-gradient-to-r from-amber-50 to-amber-100/50 border border-amber-200 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-amber-200 flex items-center justify-center text-amber-700">
                      <AlertCircle className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="font-black text-amber-800 text-lg">Outstanding Balance: ${totalOutstanding.toLocaleString()}</p>
                      <p className="text-sm text-amber-600 font-medium">Pay online now to keep your account current.</p>
                    </div>
                  </div>
                  <Button 
                    onClick={() => {
                      setPayingInvoice(null);
                      setPaymentAmount(totalOutstanding.toString());
                      setIsPaymentOpen(true);
                    }}
                    className="rounded-xl font-black bg-amber-600 hover:bg-amber-700 text-white shadow-lg shadow-amber-100"
                  >
                    <CreditCard className="w-4 h-4 mr-2" /> Pay Now
                  </Button>
                </div>
              )}

              <h3 className="text-lg font-black text-slate-800 tracking-tight">Invoices & Statements</h3>
              {invoices.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                  <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-emerald-300" />
                  <p className="font-bold">All caught up!</p>
                  <p className="text-sm mt-1">You have no outstanding invoices.</p>
                </div>
              ) : (
                invoices.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between p-5 rounded-2xl border border-slate-100 hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <p className="font-bold text-slate-900">{inv.invoice_number}</p>
                        <p className="text-xs text-slate-400 font-medium">{formatDate(inv.date)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className="font-black text-slate-900">${inv.total_amount.toLocaleString()}</p>
                        {inv.balance_due > 0 && (
                          <p className="text-xs font-bold text-amber-600">Due: ${inv.balance_due.toLocaleString()}</p>
                        )}
                      </div>
                      <Badge variant="outline" className={cn("font-bold uppercase tracking-wider text-[9px] px-2 py-0.5", statusColor(inv.status))}>
                        {inv.status}
                      </Badge>
                      {inv.balance_due > 0 && (
                        <Button 
                          size="sm" 
                          className="rounded-lg font-bold bg-blue-600 text-white hover:bg-blue-700"
                          onClick={() => {
                            setPayingInvoice(inv);
                            setPaymentAmount(inv.balance_due.toString());
                            setIsPaymentOpen(true);
                          }}
                        >
                          Pay <ChevronRight className="w-3 h-3 ml-1" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </TabsContent>

            {/* Treatment Plans Tab */}
            <TabsContent value="treatments" className="p-8 m-0 space-y-4">
              <h3 className="text-lg font-black text-slate-800 tracking-tight">Your Treatment Plans</h3>
              {treatmentPlans.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                  <Heart className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p className="font-bold">No treatment plans on file.</p>
                </div>
              ) : (
                treatmentPlans.map((plan) => (
                  <div key={plan.id} className="p-6 rounded-2xl border border-slate-100 space-y-4 hover:border-blue-200 transition-colors">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-black text-slate-900 text-lg">{plan.plan_name}</h4>
                        {plan.diagnosis && <p className="text-sm text-slate-500 font-medium mt-1">{plan.diagnosis}</p>}
                      </div>
                      <Badge variant="outline" className={cn("font-bold uppercase tracking-wider text-[9px] px-3 py-1", statusColor(plan.status))}>
                        {plan.status}
                      </Badge>
                    </div>
                    <Separator />
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Total Cost</p>
                        <p className="text-lg font-black text-slate-900">${plan.total_estimated_cost.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Insurance Covers</p>
                        <p className="text-lg font-black text-emerald-600">${plan.total_insurance_estimate.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Your Cost</p>
                        <p className="text-lg font-black text-blue-600">${plan.total_patient_responsibility.toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </TabsContent>

            {/* Insurance Tab */}
            <TabsContent value="insurance" className="p-8 m-0 space-y-4">
              <h3 className="text-lg font-black text-slate-800 tracking-tight">Insurance on File</h3>
              {insurance.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                  <Shield className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p className="font-bold">No insurance on file.</p>
                  <p className="text-sm mt-1">Contact the front desk to add your insurance.</p>
                </div>
              ) : (
                insurance.map((ins) => (
                  <div key={ins.id} className="p-6 rounded-2xl border border-slate-100 space-y-4">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center text-purple-600">
                          <Shield className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-black text-slate-900 capitalize">{ins.insurance_type} Insurance</p>
                          <p className="text-xs text-slate-400 font-medium">Member ID: {ins.subscriber_id}</p>
                        </div>
                      </div>
                      {ins.group_number && (
                        <span className="text-xs font-bold text-slate-400">Group: {ins.group_number}</span>
                      )}
                    </div>
                    <Separator />
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Annual Max</p>
                        <p className="font-black text-slate-900">${ins.annual_maximum.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Deductible</p>
                        <p className="font-black text-slate-900">${ins.annual_deductible.toLocaleString()}</p>
                        <p className="text-[10px] text-emerald-600 font-bold">${ins.deductible_met.toLocaleString()} met</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Preventive</p>
                        <p className="font-black text-emerald-600">{ins.preventive_coverage}%</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-black uppercase text-slate-400 tracking-widest">Basic / Major</p>
                        <p className="font-black text-slate-700">{ins.basic_coverage}% / {ins.major_coverage}%</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </TabsContent>
            
            {/* Digital Forms Tab */}
            <TabsContent value="forms" className="p-8 m-0 space-y-4">
              <h3 className="text-lg font-black text-slate-800 tracking-tight">Your Digital Forms</h3>
              <p className="text-slate-500 font-medium">Please complete these forms before your next visit.</p>
              
              <div className="space-y-4 mt-6">
                {documents.length === 0 ? (
                  <div className="text-center py-16 text-slate-400">
                    <FileText className="w-12 h-12 mx-auto mb-4 opacity-30" />
                    <p className="font-bold">No forms pending.</p>
                    <p className="text-sm mt-1">You are all caught up with your paperwork!</p>
                  </div>
                ) : (
                  documents.map((doc) => (
                    <div key={doc.id} className={`flex items-center justify-between p-5 rounded-2xl border border-slate-100 transition-colors ${doc.is_completed ? 'bg-slate-50/50' : 'hover:bg-blue-50/30 group'}`}>
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${doc.is_completed ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'}`}>
                          {doc.is_completed ? <CheckCircle2 className="w-6 h-6" /> : <FileText className="w-6 h-6" />}
                        </div>
                        <div>
                          <p className="font-black text-slate-900">{doc.name}</p>
                          <p className="text-sm text-slate-500 font-medium">
                            {doc.is_completed 
                              ? `Completed on ${formatDate(doc.completed_date)}`
                              : `Assigned on ${formatDate(doc.assigned_date)}`}
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-3">
                        {doc.is_completed ? (
                          <Badge variant="outline" className="font-bold uppercase tracking-wider text-[9px] px-3 py-1 bg-emerald-50 text-emerald-600 border-emerald-100">
                            Completed
                          </Badge>
                        ) : (
                          <>
                            <Badge variant="outline" className="font-bold uppercase tracking-wider text-[9px] px-3 py-1 bg-amber-50 text-amber-600 border-amber-100">
                              Signature Required
                            </Badge>
                            <Button 
                              size="sm" 
                              className="rounded-lg font-bold bg-blue-600 text-white hover:bg-blue-700"
                              onClick={() => {
                                setSigningDoc(doc);
                                setSignatureData("");
                                setSignerName("");
                                setSignatureError("");
                                setAgreedToTerms(false);
                              }}
                            >
                              Sign Now <ChevronRight className="w-3 h-3 ml-1" />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </TabsContent>
          </Card>
        </Tabs>

        {/* Electronic Signature Dialog */}
        <Dialog open={!!signingDoc} onOpenChange={(open) => { if (!open) setSigningDoc(null); }}>
          <DialogContent className="sm:max-w-[600px] rounded-3xl p-8">
            <DialogHeader>
              <DialogTitle className="text-2xl font-black text-slate-800 tracking-tight">
                Sign Digital Document
              </DialogTitle>
              <DialogDescription className="text-slate-500 font-medium">
                Please review the document and sign below to authorize.
              </DialogDescription>
            </DialogHeader>
            {signingDoc && (
              <div className="space-y-6 py-4">
                <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100 max-h-[250px] overflow-y-auto font-medium text-slate-600 text-sm leading-relaxed whitespace-pre-wrap">
                  {signingDoc.content || `By signing this document, you acknowledge that you have read and understood the patient agreement, medical history requirements, and treatment authorization for ${signingDoc.name}. You authorize the dental practice to proceed with scheduling and treatment planning under standard clinical protocols.`}
                </div>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="portal-signer-name" className="text-xs font-black uppercase tracking-widest text-slate-400">
                      Full Legal Name
                    </Label>
                    <Input
                      id="portal-signer-name"
                      value={signerName}
                      onChange={(event) => setSignerName(event.target.value)}
                      autoComplete="name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs font-black uppercase tracking-widest text-slate-400">
                      Draw Your Signature Below
                    </Label>
                    <div className="bg-slate-50 p-2 rounded-xl border border-slate-200">
                      <SignaturePad
                        width={500}
                        height={200}
                        onSave={(data) => setSignatureData(data)}
                        onClear={() => setSignatureData("")}
                      />
                    </div>
                    <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-xs text-slate-500">
                        Cannot draw a signature? Use your legal name as an accessible alternative.
                      </p>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={useTypedSignature}
                        disabled={!signerName.trim()}
                      >
                        Use Typed Name
                      </Button>
                    </div>
                    <p aria-live="polite" className="text-xs font-medium text-emerald-700">
                      {signatureData ? 'Signature captured.' : ''}
                    </p>
                  </div>
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      id="sig-agree"
                      checked={agreedToTerms}
                      onChange={(e) => setAgreedToTerms(e.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <Label htmlFor="sig-agree" className="text-xs text-slate-500 font-medium leading-relaxed cursor-pointer select-none">
                      I agree that my electronic signature above acts as a binding agreement for this clinical document.
                    </Label>
                  </div>
                  {signatureError && (
                    <p role="alert" className="text-sm font-medium text-red-600">
                      {signatureError}
                    </p>
                  )}
                </div>
              </div>
            )}
            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                variant="outline"
                onClick={() => setSigningDoc(null)}
                className="rounded-xl font-bold h-12 border-slate-200"
              >
                Cancel
              </Button>
              <Button
                disabled={!signatureData || !signerName.trim() || !agreedToTerms || isSubmittingSignature}
                onClick={async () => {
                  if (!signingDoc) return;
                  setIsSubmittingSignature(true);
                  setSignatureError('');
                  try {
                    const res = await fetch(`${API_BASE}/portal/documents/${signingDoc.id}/sign`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${session.access_token}`,
                      },
                      body: JSON.stringify({
                        signature_data: signatureData,
                        signer_name: signerName,
                        agreement_accepted: agreedToTerms,
                      }),
                    });
                    if (!res.ok) {
                      const errorBody = await res.json().catch(() => null) as { detail?: string } | null;
                      throw new Error(errorBody?.detail || 'Unable to sign the document. Please try again.');
                    }
                    await fetchData();
                    setSigningDoc(null);
                  } catch (err) {
                    setSignatureError(err instanceof Error ? err.message : 'Unable to sign the document. Please try again.');
                  } finally {
                    setIsSubmittingSignature(false);
                  }
                }}
                className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12 flex items-center justify-center gap-2"
              >
                {isSubmittingSignature ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Signing...
                  </>
                ) : (
                  'Agree & Sign'
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Online card entry is disabled until provider-hosted Stripe Elements is integrated. */}
        <Dialog open={isPaymentOpen} onOpenChange={setIsPaymentOpen}>
          <DialogContent className="sm:max-w-[500px] rounded-3xl p-8">
            <DialogHeader>
              <DialogTitle className="text-2xl font-black text-slate-800 tracking-tight">Online payment unavailable</DialogTitle>
              <DialogDescription className="text-slate-500 font-medium">
                For your security, CoreDent does not collect card numbers or CVV directly. Please contact the practice to pay this invoice until the Stripe-hosted payment form is enabled.
              </DialogDescription>
            </DialogHeader>
            {payingInvoice && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm font-semibold text-slate-700">
                Invoice {payingInvoice.invoice_number}: ${parseFloat(paymentAmount || "0").toFixed(2)}
              </div>
            )}
            <DialogFooter>
              <Button onClick={() => setIsPaymentOpen(false)} className="rounded-xl font-bold">Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        {/* Footer */}
        <div className="text-center pt-4 pb-8">
          <p className="text-xs text-slate-400 font-medium">
            <Shield className="w-3 h-3 inline mr-1" /> Your data is encrypted and HIPAA-protected.
            Contact your dental office for any questions.
          </p>
        </div>
      </main>
    </div>
  );
}

// ── Main Portal Component ────────────────────────────────────────────

export default function PatientPortal() {
  const [session, setSession] = useState<PortalSession | null>(null);
  const [linkError, setLinkError] = useState('');

  const handleLogin = (s: PortalSession) => {
    setSession(s);
    // Burn the code from the URL so a shared/copied link is not replayable.
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.has('code')) {
        url.searchParams.delete('code');
        window.history.replaceState({}, '', url.toString());
      }
    } catch { /* non-browser/test env */ }
  };

  // Magic-link click-through: /portal/verify?code=... verifies immediately.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let code: string | null = null;
      try {
        code = new URL(window.location.href).searchParams.get('code');
      } catch { code = null; }
      if (!code || session) return;
      try {
        const res = await fetch(`${API_BASE}/portal/access/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        });
        if (!res.ok) throw new Error('This sign-in link is invalid or expired.');
        const s: PortalSession = await res.json();
        if (!cancelled) handleLogin(s);
      } catch (err: any) {
        if (!cancelled) setLinkError(err.message || 'This sign-in link is invalid or expired.');
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Stable identity so PortalDashboard.fetchData (dep [access_token, onLogout])
  // does not loop on parent re-renders.
  const handleLogout = useCallback(() => {
    setSession(null);
  }, []);

  if (!session) {
    return (
      <>
        {linkError && (
          <div className="mx-auto mt-4 max-w-md p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm font-bold" role="alert">
            {linkError}
          </div>
        )}
        <PortalLogin onLogin={handleLogin} />
      </>
    );
  }

  return <PortalDashboard session={session} onLogout={handleLogout} />;
}
