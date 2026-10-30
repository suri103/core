import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Info,
  Loader2,
  Mail,
  Phone,
  ShieldCheck,
  Stethoscope,
  User,
} from 'lucide-react';
import { addDays, format, parseISO } from 'date-fns';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { toast } from '@/hooks/use-toast';
import { PageLoader } from '@/components/ui/spinner';

interface BookingPageBusinessDay {
  enabled: boolean;
  slots: { start: string; end: string }[];
}

interface AppointmentTypeOption {
  id: string;
  name: string;
  duration: string;
  description: string;
  icon: string;
}

interface BookingProvider {
  id: string;
  name: string;
}

interface IntakeFormField {
  field_id: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[] | null;
  placeholder: string | null;
}

interface BookingPage {
  practice_public_slug: string;
  page_slug: string;
  page_title: string;
  welcome_message: string | null;
  logo_url: string | null;
  primary_color: string;
  background_image_url: string | null;
  allow_new_patients: boolean;
  allow_existing_patients: boolean;
  require_phone_verification: boolean;
  require_email_verification: boolean;
  booking_window_days: number;
  min_notice_hours: number;
  practice_timezone: string;
  business_hours: Record<string, BookingPageBusinessDay>;
  blocked_dates: string[];
  allowed_appointment_types: string[];
  appointment_types: {
    id: string;
    name: string;
    duration_minutes: number;
    description: string | null;
    color?: string | null;
    icon: string | null;
  }[];
  providers: BookingProvider[];
  intake_form_fields: IntakeFormField[];
  require_insurance_info: boolean;
  require_medical_history: boolean;
  captcha_required: boolean;
}

interface TimeSlot {
  start_time: string;
  end_time: string;
  duration_minutes: number;
  is_available: boolean;
  provider_id: string | null;
  provider_name: string | null;
}

interface AvailabilityResponse {
  days: {
    date: string;
    day_of_week: string;
    is_available: boolean;
    slots: TimeSlot[];
  }[];
  total_slots: number;
}

interface BookingResponse {
  confirmation_code: string;
  status: 'pending' | 'confirmed' | 'declined' | 'cancelled' | 'completed';
  first_name: string;
  last_name: string;
  requested_date: string;
  requested_time: string;
  verification_session: string;
  require_email_verification: boolean;
  require_phone_verification: boolean;
  email_verified: boolean;
  phone_verified: boolean;
  message: string;
}

interface VerificationResponse {
  verified: boolean;
  message: string;
  confirmation_code: string | null;
  email_verified: boolean;
  phone_verified: boolean;
  require_email_verification: boolean;
  require_phone_verification: boolean;
}

interface VerificationState {
  verificationSession: string;
  confirmationCode: string | null;
  requestedDate?: string;
  requestedTime?: string;
  requireEmailVerification: boolean;
  requirePhoneVerification: boolean;
  emailVerified: boolean;
  phoneVerified: boolean;
  message: string;
  error?: string;
}

interface RecaptchaV3 {
  ready: (callback: () => void) => void;
  execute: (siteKey: string, options: { action: string }) => Promise<string>;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const RECAPTCHA_SCRIPT_ID = 'coredent-recaptcha-v3';
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;
let recaptchaLoader: Promise<RecaptchaV3> | undefined;

const isUuid = (value: unknown): value is string =>
  typeof value === 'string' && UUID_PATTERN.test(value);

const safeColor = (value: string | null | undefined) =>
  value && HEX_COLOR_PATTERN.test(value) ? value : '#2563eb';

const safePublicUrl = (value: string | null | undefined): string | undefined => {
  if (!value) return undefined;
  try {
    const parsed = new URL(value, window.location.origin);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : undefined;
  } catch {
    return undefined;
  }
};

const normalizePhone = (value: string) => {
  const trimmed = value.trim();
  const digits = trimmed.replace(/\D/g, '');
  return trimmed.startsWith('+') ? `+${digits}` : digits;
};

const dateInTimeZone = (timeZone: string) => {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  } catch {
    return format(new Date(), 'yyyy-MM-dd');
  }
};

const verificationDetailsKey = (verificationSession: string) =>
  `coredent-booking-verification:${verificationSession}`;

const VERIFICATION_DETAILS_TTL_MS = 30 * 60 * 1000; // 30min; backend expiry is authoritative

const storeVerificationDetails = (state: Pick<VerificationState, 'verificationSession' | 'requestedDate' | 'requestedTime'>) => {
  try {
    sessionStorage.setItem(verificationDetailsKey(state.verificationSession), JSON.stringify({
      requestedDate: state.requestedDate,
      requestedTime: state.requestedTime,
      storedAt: Date.now(),
    }));
  } catch {
    // Verification remains usable when browser storage is unavailable.
  }
};

const readVerificationDetails = (verificationSession: string) => {
  try {
    const raw = sessionStorage.getItem(verificationDetailsKey(verificationSession));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as { requestedDate?: unknown; requestedTime?: unknown; storedAt?: unknown };
    // Best-effort expiry for abandoned flows; backend single-use/expiry is authoritative.
    if (typeof parsed.storedAt === 'number' && Date.now() - parsed.storedAt > VERIFICATION_DETAILS_TTL_MS) {
      try { sessionStorage.removeItem(verificationDetailsKey(verificationSession)); } catch { /* ignore */ }
      return {};
    }
    return {
      requestedDate: typeof parsed.requestedDate === 'string' ? parsed.requestedDate : undefined,
      requestedTime: typeof parsed.requestedTime === 'string' ? parsed.requestedTime : undefined,
    };
  } catch {
    return {};
  }
};

const verificationComplete = (state: Pick<VerificationState,
  'requireEmailVerification' | 'requirePhoneVerification' | 'emailVerified' | 'phoneVerified'>) =>
  (!state.requireEmailVerification || state.emailVerified)
  && (!state.requirePhoneVerification || state.phoneVerified);

const getRecaptcha = (): RecaptchaV3 | undefined =>
  (window as typeof window & { grecaptcha?: RecaptchaV3 }).grecaptcha;

const loadRecaptcha = (siteKey: string): Promise<RecaptchaV3> => {
  const existingCaptcha = getRecaptcha();
  if (existingCaptcha) return Promise.resolve(existingCaptcha);
  if (recaptchaLoader) return recaptchaLoader;

  recaptchaLoader = new Promise<RecaptchaV3>((resolve, reject) => {
    const resolveCaptcha = () => {
      const captcha = getRecaptcha();
      if (captcha) resolve(captcha);
      else {
        recaptchaLoader = undefined;
        reject(new Error('CAPTCHA could not be initialized. Please try again.'));
      }
    };
    const rejectLoader = () => {
      recaptchaLoader = undefined;
      reject(new Error('CAPTCHA could not be loaded. Please try again.'));
    };
    const existingScript = document.getElementById(RECAPTCHA_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener('load', resolveCaptcha, { once: true });
      existingScript.addEventListener('error', rejectLoader, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.id = RECAPTCHA_SCRIPT_ID;
    script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(siteKey)}`;
    script.async = true;
    script.defer = true;
    script.addEventListener('load', resolveCaptcha, { once: true });
    script.addEventListener('error', rejectLoader, { once: true });
    document.head.appendChild(script);
  });
  return recaptchaLoader;
};

const getCaptchaToken = async (): Promise<string> => {
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY?.trim();
  if (!siteKey) {
    throw new Error('This practice requires CAPTCHA verification, but this page is not configured for it. Please contact the practice.');
  }
  const captcha = await loadRecaptcha(siteKey);
  await new Promise<void>((resolve, reject) => {
    try {
      captcha.ready(resolve);
    } catch {
      reject(new Error('CAPTCHA could not be initialized. Please try again.'));
    }
  });
  const token = await captcha.execute(siteKey, { action: 'booking' });
  if (!token) throw new Error('CAPTCHA verification did not return a token. Please try again.');
  return token;
};

const responseDetail = async (response: Response): Promise<string> => {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail;
  } catch {
    // Use the response status below when the server did not return JSON.
  }
  return response.statusText || `Request failed (${response.status})`;
};

const fetchPublicPage = async (practiceSlug: string, slug: string): Promise<BookingPage> => {
  const response = await fetch(`${API_BASE}/booking/public/${practiceSlug}/${slug}`, { credentials: 'include' });
  if (!response.ok) throw new Error(await responseDetail(response));
  return response.json();
};

const fetchDayAvailability = async (
  practiceSlug: string,
  slug: string,
  day: string,
  appointmentTypeId: string,
  providerId?: string,
): Promise<TimeSlot[]> => {
  const response = await fetch(`${API_BASE}/booking/public/${practiceSlug}/${slug}/availability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_date: day,
      end_date: day,
      appointment_type_id: appointmentTypeId,
      ...(providerId ? { provider_id: providerId } : {}),
    }),
  });
  if (!response.ok) throw new Error(await responseDetail(response));
  const data = await response.json() as AvailabilityResponse;
  const matchingDay = data.days.find((entry) => entry.date === day);
  if (!matchingDay) return [];
  return matchingDay.slots.map((slot) => ({
    ...slot,
    start_time: slot.start_time.slice(0, 5),
    end_time: slot.end_time.slice(0, 5),
  }));
};

const STEPS = [
  { id: 'service', title: 'Choose Service', icon: Stethoscope },
  { id: 'datetime', title: 'Date & Time', icon: Calendar },
  { id: 'info', title: 'Your Details', icon: User },
  { id: 'review', title: 'Final Review', icon: Info },
];

export default function PublicBooking() {
  const { practiceSlug, slug } = useParams<{ practiceSlug: string; slug: string }>();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedType, setSelectedType] = useState<AppointmentTypeOption | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  const [availability, setAvailability] = useState<TimeSlot[]>([]);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [phoneCode, setPhoneCode] = useState('');
  const [isVerifyingPhone, setIsVerifyingPhone] = useState(false);
  const [verificationState, setVerificationState] = useState<VerificationState | null>(null);
  const emailVerificationStarted = useRef(false);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    reason: '',
    isNewPatient: true,
    hasInsurance: false,
    insuranceCarrierName: '',
    insuranceMemberId: '',
    insuranceGroupNumber: '',
    medicalHistory: '',
    intakeResponses: {} as Record<string, string | boolean>,
  });

  const { data: page, isLoading, error: pageError } = useQuery({
    queryKey: ['public-booking-page', practiceSlug, slug],
    queryFn: () => fetchPublicPage(practiceSlug!, slug!),
    enabled: Boolean(practiceSlug && slug),
  });

  const primaryColor = safeColor(page?.primary_color);
  const logoUrl = safePublicUrl(page?.logo_url);
  const backgroundImageUrl = safePublicUrl(page?.background_image_url);
  const pageStyle: CSSProperties = backgroundImageUrl
    ? {
        backgroundImage: `linear-gradient(rgba(248,250,252,0.92), rgba(248,250,252,0.92)), url(${JSON.stringify(backgroundImageUrl)})`,
        backgroundPosition: 'center',
        backgroundSize: 'cover',
        backgroundAttachment: 'fixed',
      }
    : {};

  const availableAppointmentTypes: AppointmentTypeOption[] = (page?.appointment_types || [])
    .filter((type) => isUuid(type.id))
    .map((type) => ({
      id: type.id,
      name: type.name,
      duration: `${type.duration_minutes} min`,
      description: type.description || 'Appointment',
      icon: type.icon || '🦷',
    }));

  useEffect(() => {
    if (!page) return;
    setSelectedDate((current) => current || dateInTimeZone(page.practice_timezone));
    if (page.allow_new_patients && !page.allow_existing_patients) {
      setFormData((current) => ({ ...current, isNewPatient: true }));
    } else if (!page.allow_new_patients && page.allow_existing_patients) {
      setFormData((current) => ({ ...current, isNewPatient: false }));
    }
  }, [page]);

  const navigateToSuccess = useCallback((state: {
    verificationSession?: string;
    confirmationCode: string | null;
    requestedDate?: string;
    requestedTime?: string;
  }) => {
    if (state.verificationSession) {
      try {
        sessionStorage.removeItem(verificationDetailsKey(state.verificationSession));
      } catch {
        // Navigation must not depend on browser storage.
      }
    }
    navigate('/book/success', {
      replace: true,
      state: {
        pageTitle: page?.page_title,
        logoUrl,
        confirmationCode: state.confirmationCode,
        requestedDate: state.requestedDate,
        requestedTime: state.requestedTime,
      },
    });
  }, [logoUrl, navigate, page?.page_title]);

  useEffect(() => {
    if (!page || emailVerificationStarted.current) return;
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const verificationSession = fragment.get('verification_session');
    const emailToken = fragment.get('email_token');
    if (!verificationSession || !emailToken) return;

    emailVerificationStarted.current = true;
    const storedDetails = readVerificationDetails(verificationSession);
    setVerificationState({
      verificationSession,
      confirmationCode: null,
      requestedDate: storedDetails.requestedDate,
      requestedTime: storedDetails.requestedTime,
      requireEmailVerification: page.require_email_verification,
      requirePhoneVerification: page.require_phone_verification,
      emailVerified: !page.require_email_verification,
      phoneVerified: !page.require_phone_verification,
      message: 'Verifying your email…',
    });

    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/booking/public/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            verification_session: verificationSession,
            verification_token: emailToken,
          }),
        });
        if (!response.ok) throw new Error(await responseDetail(response));
        const result = await response.json() as VerificationResponse;
        // Failed verification returns a uniform bare response (no state
        // fields), so only a success may update the verification flags;
        // otherwise keep the state derived from the booking page.
        const nextState: VerificationState = result.verified ? {
          verificationSession,
          confirmationCode: result.confirmation_code,
          requestedDate: storedDetails.requestedDate,
          requestedTime: storedDetails.requestedTime,
          requireEmailVerification: result.require_email_verification,
          requirePhoneVerification: result.require_phone_verification,
          emailVerified: result.email_verified,
          phoneVerified: result.phone_verified,
          message: result.message,
          error: undefined,
        } : {
          verificationSession,
          confirmationCode: null,
          requestedDate: storedDetails.requestedDate,
          requestedTime: storedDetails.requestedTime,
          requireEmailVerification: page.require_email_verification,
          requirePhoneVerification: page.require_phone_verification,
          emailVerified: !page.require_email_verification,
          phoneVerified: !page.require_phone_verification,
          message: '',
          error: result.message,
        };
        setVerificationState(nextState);
        if (result.verified && verificationComplete(nextState)) navigateToSuccess(nextState);
      } catch (error) {
        setVerificationState((current) => current ? {
          ...current,
          message: '',
          error: error instanceof Error ? error.message : 'Email verification failed.',
        } : current);
      }
    })();
  }, [navigateToSuccess, page]);

  useEffect(() => {
    if (!practiceSlug || !slug || !selectedType || !selectedDate) {
      setAvailability([]);
      return;
    }
    let active = true;
    setSelectedSlot(null);
    setAvailabilityError('');
    setLoadingAvailability(true);
    void fetchDayAvailability(practiceSlug, slug, selectedDate, selectedType.id, selectedProviderId || undefined)
      .then((slots) => {
        if (active) setAvailability(slots);
      })
      .catch((error) => {
        if (active) {
          setAvailability([]);
          setAvailabilityError(error instanceof Error ? error.message : 'Availability could not be loaded.');
        }
      })
      .finally(() => {
        if (active) setLoadingAvailability(false);
      });
    return () => {
      active = false;
    };
  }, [selectedDate, selectedProviderId, selectedType, practiceSlug, slug]);

  const intakeFieldKey = (field: IntakeFormField, index: number) =>
    field.field_id || `intake-field-${index}`;
  const areRequiredIntakeFieldsComplete = () =>
    (page?.intake_form_fields || []).every((field, index) => {
      if (!field.required) return true;
      const value = formData.intakeResponses[intakeFieldKey(field, index)];
      return field.field_type === 'checkbox'
        ? value === true
        : typeof value === 'string' && value.trim().length > 0;
    });

  const isContactInfoValid = () => {
    const phoneDigits = formData.phone.replace(/\D/g, '');
    const insuranceComplete = !page?.require_insurance_info || (
      formData.hasInsurance
      && formData.insuranceCarrierName.trim().length > 0
      && formData.insuranceMemberId.trim().length > 0
    );
    return formData.firstName.trim().length >= 1
      && formData.lastName.trim().length >= 1
      && EMAIL_PATTERN.test(formData.email.trim())
      && phoneDigits.length >= 10
      && phoneDigits.length <= 15
      && Boolean(formData.dateOfBirth)
      && (!page?.require_medical_history || formData.medicalHistory.trim().length > 0)
      && insuranceComplete
      && areRequiredIntakeFieldsComplete();
  };

  const isStepComplete = () => {
    if (currentStep === 0) return Boolean(selectedType);
    if (currentStep === 1) return Boolean(selectedSlot?.provider_id && isUuid(selectedSlot.provider_id));
    if (currentStep === 2) return isContactInfoValid();
    return true;
  };

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep((step) => step + 1);
      window.scrollTo(0, 0);
    }
  };
  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((step) => step - 1);
      window.scrollTo(0, 0);
    }
  };

  const submitBooking = async () => {
    if (!page || !practiceSlug || !slug || !selectedType || !selectedSlot?.provider_id) return;
    setIsSubmitting(true);
    try {
      const captchaToken = page.captcha_required ? await getCaptchaToken() : undefined;
      const response = await fetch(`${API_BASE}/booking/public/${practiceSlug}/${slug}/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: formData.firstName.trim(),
          last_name: formData.lastName.trim(),
          email: formData.email.trim(),
          phone: normalizePhone(formData.phone),
          date_of_birth: formData.dateOfBirth,
          requested_date: selectedDate,
          requested_time: selectedSlot.start_time,
          appointment_type_id: selectedType.id,
          provider_id: selectedSlot.provider_id,
          reason: formData.reason.trim() || undefined,
          is_new_patient: formData.isNewPatient,
          has_insurance: formData.hasInsurance,
          insurance_carrier_name: formData.insuranceCarrierName.trim() || undefined,
          insurance_member_id: formData.insuranceMemberId.trim() || undefined,
          insurance_group_number: formData.insuranceGroupNumber.trim() || undefined,
          medical_history: formData.medicalHistory.trim() ? { notes: formData.medicalHistory.trim() } : {},
          intake_form_responses: formData.intakeResponses,
          captcha_token: captchaToken,
          honeypot: '',
        }),
      });
      if (!response.ok) throw new Error(await responseDetail(response));
      const result = await response.json() as BookingResponse;
      const nextState: VerificationState = {
        verificationSession: result.verification_session,
        confirmationCode: result.confirmation_code,
        requestedDate: result.requested_date,
        requestedTime: result.requested_time,
        requireEmailVerification: result.require_email_verification,
        requirePhoneVerification: result.require_phone_verification,
        emailVerified: result.email_verified,
        phoneVerified: result.phone_verified,
        message: result.message,
      };
      if (!verificationComplete(nextState)) storeVerificationDetails(nextState);
      toast({ title: 'Booking submitted', description: result.message });
      if (verificationComplete(nextState)) navigateToSuccess(nextState);
      else setVerificationState(nextState);
    } catch (error) {
      toast({
        title: 'Booking Failed',
        description: error instanceof Error ? error.message : 'An error occurred while booking.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyPhone = async () => {
    if (!verificationState || !/^\d{6}$/.test(phoneCode)) return;
    setIsVerifyingPhone(true);
    setVerificationState((current) => current ? { ...current, error: undefined } : current);
    try {
      const response = await fetch(`${API_BASE}/booking/public/verify-phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verification_session: verificationState.verificationSession,
          verification_code: phoneCode,
        }),
      });
      if (!response.ok) throw new Error(await responseDetail(response));
      const result = await response.json() as VerificationResponse;
      // Same contract as email verification: only a success carries state
      // fields, so a failure must not overwrite the flags we already hold.
      const nextState: VerificationState = result.verified ? {
        ...verificationState,
        confirmationCode: result.confirmation_code || verificationState.confirmationCode,
        requireEmailVerification: result.require_email_verification,
        requirePhoneVerification: result.require_phone_verification,
        emailVerified: result.email_verified,
        phoneVerified: result.phone_verified,
        message: result.message,
        error: undefined,
      } : {
        ...verificationState,
        message: '',
        error: result.message,
      };
      setVerificationState(nextState);
      if (result.verified && verificationComplete(nextState)) navigateToSuccess(nextState);
    } catch (error) {
      setVerificationState((current) => current ? {
        ...current,
        error: error instanceof Error ? error.message : 'Phone verification failed.',
      } : current);
    } finally {
      setIsVerifyingPhone(false);
    }
  };

  if (isLoading) return <div className="flex h-screen items-center justify-center"><PageLoader /></div>;
  if (!page || pageError) {
    return <div className="flex h-screen items-center justify-center px-4 text-center text-red-600">Booking page could not be loaded.</div>;
  }
  if (!page.allow_new_patients && !page.allow_existing_patients) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-lg"><CardContent className="p-8 text-center">
          <AlertCircle className="mx-auto mb-4 h-10 w-10 text-amber-500" />
          <h1 className="text-2xl font-black text-slate-800">Online booking is not configured</h1>
          <p className="mt-3 text-slate-600">This page is not accepting new or existing patients. Please contact the practice.</p>
        </CardContent></Card>
      </div>
    );
  }

  if (verificationState) {
    const waitingForEmail = verificationState.requireEmailVerification && !verificationState.emailVerified;
    const waitingForPhone = verificationState.requirePhoneVerification && !verificationState.phoneVerified;
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4" style={pageStyle}>
        <Card className="relative w-full max-w-xl border-none bg-white/95 shadow-2xl">
          <CardContent className="space-y-7 p-8 text-center md:p-12">
            {logoUrl && <img src={logoUrl} alt="" className="mx-auto h-16 w-16 rounded-xl object-cover" />}
            <ShieldCheck className="mx-auto h-14 w-14" style={{ color: primaryColor }} />
            <div>
              <h1 className="text-3xl font-black text-slate-800">Verify your booking request</h1>
              <p className="mt-2 text-slate-600">Complete the required verification for {page.page_title}.</p>
            </div>
            {verificationState.error && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
                {verificationState.error}
              </div>
            )}
            <div className="space-y-3 text-left">
              {verificationState.requireEmailVerification && (
                <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-4">
                  {verificationState.emailVerified ? <CheckCircle2 className="text-emerald-600" /> : <Mail className="text-blue-600" />}
                  <span className="font-semibold">{verificationState.emailVerified ? 'Email verified' : 'Check your email and open the verification link.'}</span>
                </div>
              )}
              {waitingForPhone && (
                <div className="space-y-4 rounded-xl bg-slate-50 p-4">
                  <div className="flex items-center gap-3"><Phone className="text-blue-600" /><span className="font-semibold">Enter the six-digit code sent to your phone.</span></div>
                  <Label htmlFor="phoneVerificationCode">Phone verification code</Label>
                  <Input
                    id="phoneVerificationCode"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={phoneCode}
                    onChange={(event) => setPhoneCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="123456"
                    className="text-center text-xl tracking-[0.4em]"
                  />
                  <Button
                    onClick={verifyPhone}
                    disabled={!/^\d{6}$/.test(phoneCode) || isVerifyingPhone}
                    className="w-full text-white"
                    style={{ backgroundColor: primaryColor }}
                  >
                    {isVerifyingPhone ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Verifying…</> : 'Verify phone'}
                  </Button>
                </div>
              )}
            </div>
            {waitingForEmail && !waitingForPhone && <p className="text-sm text-slate-500">You can leave this page and continue from the secure link in your email.</p>}
          </CardContent>
        </Card>
      </div>
    );
  }

  const calendarDays = Math.max(1, page.booking_window_days + 1);
  const practiceToday = dateInTimeZone(page.practice_timezone);
  const visibleSlots = availability.filter((slot) => slot.is_available && isUuid(slot.provider_id));
  const minNoticeCopy = page.min_notice_hours === 0
    ? 'Same-day times may be available.'
    : `Appointments require at least ${page.min_notice_hours} hour${page.min_notice_hours === 1 ? '' : 's'}' notice.`;

  return (
    <div className="min-h-screen overflow-x-hidden bg-slate-50 pb-20 font-sans text-slate-900" style={pageStyle}>
      <header className="relative z-10 w-full px-4 pb-8 pt-12 text-center">
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-4">
          {logoUrl && <img src={logoUrl} alt={`${page.page_title} logo`} className="h-20 w-20 rounded-2xl border-4 border-white object-cover shadow-2xl" />}
          <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">{page.page_title}</h1>
          {page.welcome_message && <p className="max-w-md text-lg leading-relaxed text-slate-500">{page.welcome_message}</p>}
          <p className="text-xs font-semibold text-slate-400">Times shown in {page.practice_timezone}</p>
        </motion.div>
      </header>

      <main className="container relative z-10 mx-auto mt-4 max-w-4xl px-4">
        <div className="mb-10 px-2 lg:px-0">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-sm font-semibold uppercase tracking-wider text-slate-500">Step {currentStep + 1} of {STEPS.length}</span>
            <span className="text-sm font-bold" style={{ color: primaryColor }}>{Math.round(((currentStep + 1) / STEPS.length) * 100)}% Complete</span>
          </div>
          <Progress value={((currentStep + 1) / STEPS.length) * 100} className="h-2 rounded-full bg-slate-200" />
          <div className="mt-6 hidden justify-between px-1 md:flex">
            {STEPS.map((step, index) => (
              <div key={step.id} className={cn('flex items-center gap-2', currentStep >= index ? 'text-slate-800' : 'text-slate-400 opacity-60')}>
                <div className="flex h-8 w-8 items-center justify-center rounded-full border-2" style={currentStep >= index ? { borderColor: primaryColor, color: currentStep === index ? '#fff' : primaryColor, backgroundColor: currentStep === index ? primaryColor : '#fff' } : undefined}>
                  {currentStep > index ? <CheckCircle2 className="h-5 w-5" /> : <step.icon className="h-4 w-4" />}
                </div>
                <span className="text-sm font-bold">{step.title}</span>
              </div>
            ))}
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={currentStep} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            <Card className="overflow-hidden rounded-3xl border-none bg-white/90 shadow-[0_20px_50px_rgba(0,0,0,0.08)] backdrop-blur-xl">
              <CardContent className="p-8 md:p-12">
                {currentStep === 0 && (
                  <div className="space-y-8">
                    <div><h2 className="text-2xl font-black">What brings you in today?</h2><p className="mt-2 text-slate-500">Select one of the services configured by this practice.</p></div>
                    {availableAppointmentTypes.length === 0 ? (
                      <div role="status" className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
                        <h3 className="font-extrabold">No services are currently available online</h3>
                        <p className="mt-1 text-sm">Please contact the practice to request an appointment.</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        {availableAppointmentTypes.map((type) => (
                          <button
                            key={type.id}
                            onClick={() => { setSelectedType(type); setSelectedSlot(null); setCurrentStep(1); }}
                            className="rounded-2xl border-2 bg-white p-6 text-left transition hover:shadow-xl"
                            style={selectedType?.id === type.id ? { borderColor: primaryColor, backgroundColor: primaryColor, color: '#fff' } : { borderColor: '#e2e8f0' }}
                          >
                            <div className="mb-4 flex items-start justify-between"><span className="text-4xl">{type.icon}</span><Badge variant="outline">{type.duration}</Badge></div>
                            <h3 className="text-xl font-extrabold">{type.name}</h3>
                            <p className="mt-1 text-sm opacity-80">{type.description}</p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {currentStep === 1 && (
                  <div className="space-y-8">
                    <div><h2 className="text-2xl font-black">Pick a convenient time</h2><p className="mt-2 text-slate-500">{minNoticeCopy}</p></div>
                    {page.providers.length > 0 && (
                      <div className="max-w-md space-y-2">
                        <Label htmlFor="provider">Preferred provider (Optional)</Label>
                        <select id="provider" value={selectedProviderId} onChange={(event) => setSelectedProviderId(event.target.value)} className="h-12 w-full rounded-xl border border-slate-200 bg-white px-4">
                          <option value="">Any available provider</option>
                          {page.providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
                        </select>
                      </div>
                    )}
                    <div className="flex flex-col gap-10 lg:flex-row">
                      <div className="flex-1 space-y-4">
                        <Label className="uppercase tracking-wider text-slate-400">Available Dates</Label>
                        <div className="grid grid-cols-7 gap-2">
                          {Array.from({ length: calendarDays }, (_, index) => {
                            const date = format(addDays(parseISO(practiceToday), index), 'yyyy-MM-dd');
                            const selected = date === selectedDate;
                            const displayDate = parseISO(date);
                            return (
                              <button key={date} onClick={() => setSelectedDate(date)} className="flex flex-col items-center rounded-xl border-2 p-2" style={selected ? { borderColor: primaryColor, backgroundColor: primaryColor, color: '#fff' } : { borderColor: 'transparent', backgroundColor: '#f8fafc' }}>
                                <span className="text-[10px] font-black uppercase">{format(displayDate, 'eee')}</span><span className="text-lg font-black">{format(displayDate, 'd')}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                      <div className="space-y-4 lg:w-[300px]">
                        <Label className="uppercase tracking-wider text-slate-400">Preferred Time</Label>
                        {loadingAvailability ? <div className="py-10 text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin" /></div>
                          : availabilityError ? <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{availabilityError}</div>
                          : visibleSlots.length === 0 ? <div className="py-10 text-center text-sm text-slate-400">No slots available on this date.</div>
                          : <div className="max-h-[320px] space-y-2 overflow-y-auto pr-2">{visibleSlots.map((slot) => (
                            <button key={`${slot.start_time}-${slot.provider_id}`} onClick={() => setSelectedSlot(slot)} className="w-full rounded-xl border-2 p-4 text-left" style={selectedSlot?.start_time === slot.start_time && selectedSlot.provider_id === slot.provider_id ? { borderColor: primaryColor, backgroundColor: primaryColor, color: '#fff' } : { borderColor: '#e2e8f0' }}>
                              <span className="flex items-center gap-2 text-lg font-black"><Clock className="h-4 w-4" />{slot.start_time}</span>
                              <span className="mt-1 block text-xs opacity-75">with {slot.provider_name}</span>
                            </button>
                          ))}</div>}
                      </div>
                    </div>
                  </div>
                )}

                {currentStep === 2 && (
                  <div className="space-y-8">
                    <div><h2 className="text-2xl font-black">Tell us about yourself</h2><p className="mt-2 text-slate-500">All fields marked required must be completed.</p></div>
                    {page.allow_new_patients && page.allow_existing_patients && (
                      <fieldset className="space-y-3"><legend className="text-sm font-bold">Patient status</legend><div className="flex gap-6">
                        <label className="flex items-center gap-2"><input type="radio" name="patientMode" checked={formData.isNewPatient} onChange={() => setFormData((current) => ({ ...current, isNewPatient: true }))} /> New patient</label>
                        <label className="flex items-center gap-2"><input type="radio" name="patientMode" checked={!formData.isNewPatient} onChange={() => setFormData((current) => ({ ...current, isNewPatient: false }))} /> Existing patient</label>
                      </div></fieldset>
                    )}
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                      <div className="space-y-2"><Label htmlFor="firstName">First Name</Label><Input id="firstName" value={formData.firstName} onChange={(event) => setFormData((current) => ({ ...current, firstName: event.target.value }))} /></div>
                      <div className="space-y-2"><Label htmlFor="lastName">Last Name</Label><Input id="lastName" value={formData.lastName} onChange={(event) => setFormData((current) => ({ ...current, lastName: event.target.value }))} /></div>
                      <div className="space-y-2"><Label htmlFor="email">Email Address</Label><Input id="email" type="email" value={formData.email} onChange={(event) => setFormData((current) => ({ ...current, email: event.target.value }))} /></div>
                      <div className="space-y-2"><Label htmlFor="phone">Phone Number</Label><Input id="phone" type="tel" value={formData.phone} onChange={(event) => setFormData((current) => ({ ...current, phone: event.target.value }))} /><p className="text-xs text-slate-500">Enter 10–15 digits.</p></div>
                      <div className="space-y-2"><Label htmlFor="dateOfBirth">Date of Birth</Label><Input id="dateOfBirth" type="date" required value={formData.dateOfBirth} onChange={(event) => setFormData((current) => ({ ...current, dateOfBirth: event.target.value }))} /></div>
                    </div>
                    <div className="space-y-2"><Label htmlFor="reason">Reason for visit (Optional)</Label><Textarea id="reason" value={formData.reason} onChange={(event) => setFormData((current) => ({ ...current, reason: event.target.value }))} /></div>

                    {page.require_insurance_info && (
                      <div className="space-y-4 rounded-2xl border border-blue-100 bg-blue-50/50 p-6">
                        <h3 className="text-lg font-extrabold">Insurance information</h3>
                        <label className="flex items-center gap-2"><input type="checkbox" checked={formData.hasInsurance} onChange={(event) => setFormData((current) => ({ ...current, hasInsurance: event.target.checked }))} /> I have active dental insurance</label>
                        <div className="grid gap-4 md:grid-cols-2">
                          <div><Label htmlFor="insuranceCarrierName">Insurance carrier</Label><Input id="insuranceCarrierName" value={formData.insuranceCarrierName} onChange={(event) => setFormData((current) => ({ ...current, insuranceCarrierName: event.target.value }))} /></div>
                          <div><Label htmlFor="insuranceMemberId">Member ID</Label><Input id="insuranceMemberId" value={formData.insuranceMemberId} onChange={(event) => setFormData((current) => ({ ...current, insuranceMemberId: event.target.value }))} /></div>
                          <div><Label htmlFor="insuranceGroupNumber">Group number (Optional)</Label><Input id="insuranceGroupNumber" value={formData.insuranceGroupNumber} onChange={(event) => setFormData((current) => ({ ...current, insuranceGroupNumber: event.target.value }))} /></div>
                        </div>
                      </div>
                    )}
                    {page.require_medical_history && <div className="space-y-2"><Label htmlFor="medicalHistory">Medical history</Label><Textarea id="medicalHistory" value={formData.medicalHistory} onChange={(event) => setFormData((current) => ({ ...current, medicalHistory: event.target.value }))} /></div>}
                    {page.intake_form_fields.length > 0 && (
                      <div className="space-y-5 rounded-2xl border p-6"><h3 className="text-lg font-extrabold">Additional information</h3>
                        {page.intake_form_fields.map((field, index) => {
                          const key = intakeFieldKey(field, index);
                          const value = formData.intakeResponses[key];
                          const setValue = (next: string | boolean) => setFormData((current) => ({ ...current, intakeResponses: { ...current.intakeResponses, [key]: next } }));
                          if (field.field_type === 'checkbox') return <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={value === true} onChange={(event) => setValue(event.target.checked)} />{field.label}{field.required ? ' *' : ''}</label>;
                          return <div key={key} className="space-y-2"><Label htmlFor={key}>{field.label}{field.required ? ' *' : ''}</Label>
                            {field.field_type === 'textarea' ? <Textarea id={key} value={typeof value === 'string' ? value : ''} onChange={(event) => setValue(event.target.value)} />
                              : ['select', 'radio'].includes(field.field_type) ? <select id={key} className="h-12 w-full rounded-xl border px-4" value={typeof value === 'string' ? value : ''} onChange={(event) => setValue(event.target.value)}><option value="">Select an option</option>{(field.options || []).map((option) => <option key={option}>{option}</option>)}</select>
                              : <Input id={key} type={['date', 'email', 'number', 'tel'].includes(field.field_type) ? field.field_type : 'text'} placeholder={field.placeholder || undefined} value={typeof value === 'string' ? value : ''} onChange={(event) => setValue(event.target.value)} />}
                          </div>;
                        })}
                      </div>
                    )}
                    {page.captcha_required && <div className="flex gap-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600"><AlertCircle className="h-5 w-5" /> CAPTCHA verification will run when you submit.</div>}
                  </div>
                )}

                {currentStep === 3 && (
                  <div className="space-y-8">
                    <div className="text-center"><CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500" /><h2 className="mt-4 text-3xl font-black">Almost there!</h2><p className="mt-2 text-slate-500">Review your booking request.</p></div>
                    <div className="grid gap-6 rounded-2xl bg-slate-50 p-7 md:grid-cols-2">
                      <div><p className="text-xs font-black uppercase text-slate-400">Patient</p><p className="text-lg font-bold">{formData.firstName} {formData.lastName}</p><p className="text-sm text-slate-500">{formData.isNewPatient ? 'New patient' : 'Existing patient'}</p></div>
                      <div><p className="text-xs font-black uppercase text-slate-400">Service</p><p className="text-lg font-bold">{selectedType?.name}</p></div>
                      <div><p className="text-xs font-black uppercase text-slate-400">Date & time</p><p className="text-lg font-bold">{selectedDate ? format(parseISO(selectedDate), 'EEEE, MMMM d, yyyy') : ''} at {selectedSlot?.start_time}</p></div>
                      <div><p className="text-xs font-black uppercase text-slate-400">Provider</p><p className="text-lg font-bold">{selectedSlot?.provider_name}</p></div>
                    </div>
                    <div className="flex gap-3 rounded-xl bg-amber-50 p-5 text-sm text-amber-900"><AlertCircle className="h-5 w-5 shrink-0" /><p>This is a request until practice staff confirm it.</p></div>
                  </div>
                )}
              </CardContent>

              <div className="flex items-center justify-between gap-4 border-t bg-slate-50/60 p-6">
                <Button variant="ghost" onClick={handleBack} disabled={currentStep === 0}><ChevronLeft className="mr-1 h-5 w-5" /> Back</Button>
                {currentStep === STEPS.length - 1 ? (
                  <Button onClick={submitBooking} disabled={isSubmitting} className="text-white" style={{ backgroundColor: primaryColor }}>
                    {isSubmitting ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" />Submitting…</> : <>Confirm Booking <ArrowRight className="ml-2 h-5 w-5" /></>}
                  </Button>
                ) : (
                  <Button onClick={handleNext} disabled={!isStepComplete()} className="text-white" style={{ backgroundColor: primaryColor }}>Continue <ChevronRight className="ml-2 h-5 w-5" /></Button>
                )}
              </div>
            </Card>
          </motion.div>
        </AnimatePresence>
        <p className="mt-10 text-center text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Powered by CoreDent Prime</p>
      </main>
    </div>
  );
}
