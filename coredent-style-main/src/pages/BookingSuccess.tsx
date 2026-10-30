import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Calendar, CheckCircle2, Clock, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface BookingSuccessState {
  pageTitle?: unknown;
  logoUrl?: unknown;
  confirmationCode?: unknown;
  requestedDate?: unknown;
  requestedTime?: unknown;
}

const asText = (value: unknown) => typeof value === 'string' && value.trim() ? value.trim() : undefined;

const safePublicUrl = (value: unknown): string | undefined => {
  const raw = asText(value);
  if (!raw) return undefined;
  try {
    const parsed = new URL(raw, window.location.origin);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : undefined;
  } catch {
    return undefined;
  }
};

const displayDate = (value: string | undefined) => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date(year, month - 1, day));
};

export default function BookingSuccess() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state && typeof location.state === 'object'
    ? location.state
    : {}) as BookingSuccessState;
  const pageTitle = asText(state.pageTitle);
  const logoUrl = safePublicUrl(state.logoUrl);
  const confirmationCode = asText(state.confirmationCode);
  const requestedDate = asText(state.requestedDate);
  const requestedTime = asText(state.requestedTime)?.slice(0, 5);
  const hasBookingState = Boolean(pageTitle || confirmationCode || requestedDate || requestedTime);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="pointer-events-none fixed inset-0 overflow-hidden opacity-20">
        <div className="absolute right-[-10%] top-[-10%] h-[50%] w-[50%] rounded-full bg-emerald-400 blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-10%] h-[50%] w-[50%] rounded-full bg-blue-300 blur-[120px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 w-full max-w-2xl"
      >
        <Card className="overflow-hidden rounded-[2.5rem] border-none bg-white/95 shadow-[0_30px_70px_rgba(0,0,0,0.08)] backdrop-blur-xl">
          <CardContent className="space-y-8 p-8 text-center md:p-12">
            {logoUrl && <img src={logoUrl} alt="" className="mx-auto h-16 w-16 rounded-xl object-cover shadow" />}
            <div className="flex justify-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.15, type: 'spring', stiffness: 200 }}
                className={hasBookingState
                  ? 'flex h-24 w-24 items-center justify-center rounded-full bg-emerald-500 text-white shadow-2xl shadow-emerald-200'
                  : 'flex h-24 w-24 items-center justify-center rounded-full bg-slate-200 text-slate-500'}
              >
                {hasBookingState
                  ? <CheckCircle2 className="h-12 w-12" />
                  : <ShieldCheck className="h-12 w-12" />}
              </motion.div>
            </div>

            <div className="space-y-3">
              <h1 className="text-4xl font-black tracking-tight text-slate-800">
                {hasBookingState ? 'Booking Requested!' : 'Booking details unavailable'}
              </h1>
              <p className="mx-auto max-w-md text-lg text-slate-500">
                {hasBookingState
                  ? pageTitle
                    ? <>Your verified request has been sent to <span className="font-bold text-slate-900">{pageTitle}</span>.</>
                    : 'Your verified booking request has been sent to the practice.'
                  : 'No verified booking details were provided. Return home or use the original booking link to start again.'}
              </p>
            </div>

            {(confirmationCode || requestedDate || requestedTime) && (
              <div className="rounded-2xl bg-slate-50 p-6 text-left">
                {confirmationCode && (
                  <div className="mb-5">
                    <p className="text-xs font-black uppercase tracking-widest text-slate-400">Confirmation code</p>
                    <p className="mt-1 font-mono text-2xl font-black text-slate-800">{confirmationCode}</p>
                  </div>
                )}
                {(requestedDate || requestedTime) && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {requestedDate && <div className="flex items-start gap-3"><Calendar className="mt-0.5 h-5 w-5 text-blue-600" /><div><p className="text-xs font-black uppercase text-slate-400">Requested date</p><p className="font-bold text-slate-700">{displayDate(requestedDate)}</p></div></div>}
                    {requestedTime && <div className="flex items-start gap-3"><Clock className="mt-0.5 h-5 w-5 text-blue-600" /><div><p className="text-xs font-black uppercase text-slate-400">Requested time</p><p className="font-bold text-slate-700">{requestedTime}</p></div></div>}
                  </div>
                )}
              </div>
            )}

            {hasBookingState && (
              <div className="flex items-start gap-4 rounded-2xl bg-emerald-50 p-5 text-left">
                <ShieldCheck className="h-6 w-6 shrink-0 text-emerald-600" />
                <div><p className="font-bold text-emerald-900">Request verified</p><p className="mt-1 text-sm text-emerald-800">Practice staff will review the request and contact you to confirm the appointment.</p></div>
              </div>
            )}

            <Button
              onClick={() => navigate('/')}
              variant="outline"
              className="h-14 rounded-2xl border-none bg-slate-100 px-8 font-black text-slate-700 hover:bg-slate-200"
            >
              <ArrowLeft className="mr-2 h-5 w-5" /> Return Home
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
