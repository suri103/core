/**
 * Staff online booking operations.
 *
 * This page deliberately uses only the booking APIs. It does not invent
 * request counts, patient records, or booking settings that the backend has
 * not returned.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar, CheckCircle2, Clock, Copy, Link2, Search, UserRound, Users, XCircle } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { patientsApi } from '@/services/api';
import {
  bookingApi,
  type BookingPage,
  type BookingStatus,
  type OnlineBooking,
  type WaitlistStatus,
} from '@/services/bookingApi';
import type { ApiResponse, Patient, PaginatedResponse } from '@/types/api';
import { useToast } from '@/hooks/use-toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

async function requireData<T>(response: ApiResponse<T>): Promise<T> {
  if (!response.success || response.data === undefined) {
    throw new Error(response.error?.message || 'The booking service did not return data.');
  }
  return response.data;
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed);
}

function formatTime(value: string): string {
  const [hours, minutes] = value.split(':').map(Number);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return value;
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const hour = hours % 12 || 12;
  return `${hour}:${String(minutes).padStart(2, '0')} ${suffix}`;
}

function statusLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function statusVariant(status: BookingStatus | WaitlistStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'confirmed' || status === 'booked') return 'default';
  if (status === 'declined' || status === 'cancelled' || status === 'expired') return 'destructive';
  if (status === 'pending' || status === 'active' || status === 'notified') return 'secondary';
  return 'outline';
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The booking service is temporarily unavailable.';
}

export default function OnlineBooking() {
  const { hasRole } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const canConfigurePages = hasRole('owner', 'admin');
  const [searchTerm, setSearchTerm] = useState('');
  const [associationBooking, setAssociationBooking] = useState<OnlineBooking | null>(null);
  const [patientSearch, setPatientSearch] = useState('');

  const pagesQuery = useQuery({
    queryKey: ['booking', 'pages'],
    enabled: canConfigurePages,
    queryFn: async () => requireData(await bookingApi.listPages({ limit: 20 })),
  });
  const bookingsQuery = useQuery({
    queryKey: ['booking', 'bookings'],
    queryFn: async () => requireData(await bookingApi.listBookings({ limit: 100 })),
  });
  const waitlistQuery = useQuery({
    queryKey: ['booking', 'waitlist'],
    queryFn: async () => requireData(await bookingApi.listWaitlist({ limit: 100 })),
  });

  const patientsQuery = useQuery({
    queryKey: ['booking', 'patient-association', patientSearch],
    enabled: associationBooking !== null,
    queryFn: async () => {
      const response = await patientsApi.list({ search: patientSearch || undefined, status: 'active', page: 1, limit: 20 });
      return requireData(response as ApiResponse<PaginatedResponse<Patient>>);
    },
  });

  const refreshBookingData = () => {
    void queryClient.invalidateQueries({ queryKey: ['booking'] });
  };

  const updateBookingMutation = useMutation({
    mutationFn: ({ bookingId, payload }: { bookingId: string; payload: { status?: BookingStatus; patient_id?: string } }) =>
      bookingApi.updateBooking(bookingId, payload).then(requireData),
    onSuccess: (_data, variables) => {
      setAssociationBooking(null);
      toast({ title: variables.payload.patient_id ? 'Patient associated' : 'Booking updated' });
      refreshBookingData();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Booking update failed', description: errorMessage(error) }),
  });

  const confirmMutation = useMutation({
    mutationFn: (booking: OnlineBooking) => bookingApi.confirmBooking(booking.id, {
      booking_id: booking.id,
      create_appointment: true,
      send_confirmation: true,
    }).then(requireData),
    onSuccess: (result) => {
      toast({ title: 'Booking confirmed', description: result.appointment_id ? 'The appointment was created.' : 'The booking was confirmed.' });
      refreshBookingData();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Booking confirmation failed', description: errorMessage(error) }),
  });

  const notifyWaitlistMutation = useMutation({
    mutationFn: (entryId: string) => bookingApi.notifyWaitlist(entryId).then(requireData),
    onSuccess: (result) => {
      toast({
        title: result.provider_accepted ? 'Notification accepted' : 'Notification not accepted',
        description: result.message,
        variant: result.provider_accepted ? 'default' : 'destructive',
      });
      refreshBookingData();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Waitlist notification failed', description: errorMessage(error) }),
  });

  const updateWaitlistMutation = useMutation({
    mutationFn: ({ entryId, status }: { entryId: string; status: WaitlistStatus }) =>
      bookingApi.updateWaitlist(entryId, { status }).then(requireData),
    onSuccess: () => {
      toast({ title: 'Waitlist updated' });
      refreshBookingData();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Waitlist update failed', description: errorMessage(error) }),
  });

  const pageData = pagesQuery.data?.pages;
  const bookingData = bookingsQuery.data?.bookings;
  const waitlistData = waitlistQuery.data?.entries;
  const pages = useMemo(() => pageData ?? [], [pageData]);
  const bookings = useMemo(() => bookingData ?? [], [bookingData]);
  const waitlist = useMemo(() => waitlistData ?? [], [waitlistData]);
  const activePage: BookingPage | undefined = pages.find((page) => page.status === 'active');
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredBookings = useMemo(
    () => bookings.filter((booking) => [
      booking.first_name,
      booking.last_name,
      booking.email,
      booking.confirmation_code,
      booking.status,
    ].some((value) => value.toLowerCase().includes(normalizedSearch))),
    [bookings, normalizedSearch],
  );
  const filteredWaitlist = useMemo(
    () => waitlist.filter((entry) => [entry.first_name, entry.last_name, entry.email, entry.status]
      .some((value) => value.toLowerCase().includes(normalizedSearch))),
    [waitlist, normalizedSearch],
  );
  const pendingCount = bookings.filter((booking) => booking.status === 'pending').length;
  const confirmedCount = bookings.filter((booking) => booking.status === 'confirmed').length;
  const queryError = bookingsQuery.error || waitlistQuery.error || (canConfigurePages ? pagesQuery.error : null);

  const copyBookingLink = async () => {
    if (!activePage) return;
    const link = `${window.location.origin}/book/${encodeURIComponent(activePage.practice_public_slug)}/${encodeURIComponent(activePage.page_slug)}`;
    try {
      await navigator.clipboard.writeText(link);
      toast({ title: 'Booking link copied' });
    } catch {
      toast({ variant: 'destructive', title: 'Could not copy booking link', description: link });
    }
  };

  return (
    <div className="container mx-auto space-y-6 py-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-bold">Online Booking</h1>
          <p className="text-muted-foreground">Review live booking requests, confirmations, and waitlist activity.</p>
        </div>
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <Input
            aria-label="Search booking requests"
            className="pl-9"
            placeholder="Search requests or waitlist"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </div>
      </div>

      {queryError && (
        <Alert variant="destructive">
          <AlertTitle>Booking data unavailable</AlertTitle>
          <AlertDescription>{errorMessage(queryError)}</AlertDescription>
        </Alert>
      )}

      {canConfigurePages && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="h-5 w-5" />Patient booking link</CardTitle></CardHeader>
          <CardContent>
            {pagesQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading booking pages…</p> : activePage ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <Input readOnly value={`${window.location.origin}/book/${encodeURIComponent(activePage.practice_public_slug)}/${encodeURIComponent(activePage.page_slug)}`} aria-label="Patient booking link" />
                <Button type="button" variant="outline" onClick={copyBookingLink}><Copy className="mr-2 h-4 w-4" />Copy link</Button>
              </div>
            ) : <p className="text-sm text-muted-foreground">No active booking page is configured for this practice.</p>}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><CardContent className="flex items-center gap-3 p-5"><Clock className="h-5 w-5 text-amber-600" /><div><p className="text-sm text-muted-foreground">Pending requests</p><p className="text-2xl font-bold">{bookingsQuery.isLoading ? '…' : pendingCount}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><div><p className="text-sm text-muted-foreground">Confirmed requests</p><p className="text-2xl font-bold">{bookingsQuery.isLoading ? '…' : confirmedCount}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><Users className="h-5 w-5 text-blue-600" /><div><p className="text-sm text-muted-foreground">Active waitlist</p><p className="text-2xl font-bold">{waitlistQuery.isLoading ? '…' : waitlist.filter((entry) => ['active', 'notified'].includes(entry.status)).length}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><Calendar className="h-5 w-5 text-slate-600" /><div><p className="text-sm text-muted-foreground">Requests loaded</p><p className="text-2xl font-bold">{bookingsQuery.isLoading ? '…' : bookingsQuery.data?.total ?? bookings.length}</p></div></CardContent></Card>
      </div>

      <Tabs defaultValue="requests" className="space-y-4">
        <TabsList>
          <TabsTrigger value="requests">Booking requests</TabsTrigger>
          <TabsTrigger value="waitlist">Waitlist</TabsTrigger>
        </TabsList>

        <TabsContent value="requests">
          <Card>
            <CardHeader><CardTitle>Booking requests</CardTitle></CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow><TableHead>Patient</TableHead><TableHead>Requested slot</TableHead><TableHead>Contact</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                <TableBody>
                  {filteredBookings.map((booking) => {
                    const needsPatient = !booking.is_new_patient && !booking.patient_id;
                    return (
                      <TableRow key={booking.id}>
                        <TableCell>
                          <div className="flex items-start gap-2"><UserRound className="mt-0.5 h-4 w-4 text-muted-foreground" /><div><p className="font-medium">{booking.first_name} {booking.last_name}</p><p className="text-xs text-muted-foreground">{booking.is_new_patient ? 'New patient' : booking.patient_id ? 'Patient associated' : 'Existing patient needs association'}</p></div></div>
                        </TableCell>
                        <TableCell><p>{formatDate(booking.requested_date)}</p><p className="text-xs text-muted-foreground">{formatTime(booking.requested_time)} · {booking.duration_minutes} min</p></TableCell>
                        <TableCell><p>{booking.email}</p><p className="text-xs text-muted-foreground">{booking.phone}</p></TableCell>
                        <TableCell><Badge variant={statusVariant(booking.status)}>{statusLabel(booking.status)}</Badge></TableCell>
                        <TableCell>
                          <div className="flex flex-wrap justify-end gap-2">
                            {needsPatient && booking.status === 'pending' && <Button size="sm" variant="outline" onClick={() => { setAssociationBooking(booking); setPatientSearch(''); }}>Associate patient</Button>}
                            {booking.status === 'pending' && <>
                              <Button size="sm" disabled={needsPatient || confirmMutation.isPending} onClick={() => confirmMutation.mutate(booking)} title={needsPatient ? 'Associate the existing patient before confirming' : undefined}>Confirm & schedule</Button>
                              <Button size="sm" variant="outline" disabled={updateBookingMutation.isPending} onClick={() => updateBookingMutation.mutate({ bookingId: booking.id, payload: { status: 'declined' } })}>Decline</Button>
                            </>}
                            {booking.status === 'confirmed' && <Button size="sm" variant="outline" disabled={updateBookingMutation.isPending} onClick={() => updateBookingMutation.mutate({ bookingId: booking.id, payload: { status: 'cancelled' } })}>Cancel</Button>}
                            {booking.status === 'pending' && needsPatient && <span className="flex items-center text-xs text-amber-700"><XCircle className="mr-1 h-3.5 w-3.5" />Association required</span>}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {!bookingsQuery.isLoading && filteredBookings.length === 0 && <TableRow><TableCell colSpan={5} className="h-24 text-center text-muted-foreground">No booking requests match this search.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="waitlist">
          <Card>
            <CardHeader><CardTitle>Waitlist</CardTitle></CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow><TableHead>Patient</TableHead><TableHead>Preferences</TableHead><TableHead>Status</TableHead><TableHead>Notifications</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                <TableBody>
                  {filteredWaitlist.map((entry) => <TableRow key={entry.id}>
                    <TableCell><p className="font-medium">{entry.first_name} {entry.last_name}</p><p className="text-xs text-muted-foreground">{entry.email}</p></TableCell>
                    <TableCell><p>{entry.preferred_dates.length ? entry.preferred_dates.map(formatDate).join(', ') : 'Any date'}</p><p className="text-xs text-muted-foreground">{entry.preferred_times.length ? entry.preferred_times.join(', ') : 'Any time'}</p></TableCell>
                    <TableCell><Badge variant={statusVariant(entry.status)}>{statusLabel(entry.status)}</Badge></TableCell>
                    <TableCell>{entry.notified_count}</TableCell>
                    <TableCell><div className="flex flex-wrap justify-end gap-2">{['active', 'notified'].includes(entry.status) && <Button size="sm" variant="outline" disabled={notifyWaitlistMutation.isPending} onClick={() => notifyWaitlistMutation.mutate(entry.id)}>Notify</Button>}{entry.status !== 'cancelled' && entry.status !== 'booked' && <Button size="sm" variant="ghost" disabled={updateWaitlistMutation.isPending} onClick={() => updateWaitlistMutation.mutate({ entryId: entry.id, status: 'cancelled' })}>Remove</Button>}</div></TableCell>
                  </TableRow>)}
                  {!waitlistQuery.isLoading && filteredWaitlist.length === 0 && <TableRow><TableCell colSpan={5} className="h-24 text-center text-muted-foreground">No waitlist entries match this search.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={associationBooking !== null} onOpenChange={(open) => !open && setAssociationBooking(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Associate an existing patient</DialogTitle>
            <DialogDescription>Select the tenant-scoped patient record that matches this booking request.</DialogDescription>
          </DialogHeader>
          <Input placeholder="Search by patient name" value={patientSearch} onChange={(event) => setPatientSearch(event.target.value)} aria-label="Search patients" />
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {patientsQuery.isLoading && <p className="text-sm text-muted-foreground">Searching patients…</p>}
            {patientsQuery.error && <p className="text-sm text-destructive">{errorMessage(patientsQuery.error)}</p>}
            {(patientsQuery.data?.data ?? []).map((patient) => <Button key={patient.id} type="button" variant="outline" className="h-auto w-full justify-start py-3 text-left" disabled={updateBookingMutation.isPending} onClick={() => associationBooking && updateBookingMutation.mutate({ bookingId: associationBooking.id, payload: { patient_id: patient.id } })}><span><span className="block font-medium">{patient.firstName} {patient.lastName}</span><span className="block text-xs text-muted-foreground">{patient.email} · {patient.phone}</span></span></Button>)}
            {!patientsQuery.isLoading && patientsQuery.data?.data.length === 0 && <p className="text-sm text-muted-foreground">No active patients found.</p>}
          </div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setAssociationBooking(null)}>Close</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
