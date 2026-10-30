/**
 * Appointments Page
 * Detailed appointment management
 */

import { useState, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { logger } from "@/lib/logger";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Search, 
  Plus, 
  Calendar, 
  Clock, 
  User,
  CheckCircle,
  XCircle,
  AlertCircle,
  Edit,
  Trash2,
  Send,
  Loader2
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  useAppointments,
  useAppointmentStats,
  useAppointmentTypes,
  useCreateAppointment,
  useUpdateAppointment,
  useDeleteAppointment,
  useSendAppointmentReminder,
} from "@/hooks/useAppointments";
import { AppointmentForm } from "@/components/appointments/AppointmentForm";
import type { Appointment } from "@/services/appointmentsApi";

// Dev/test-only flag: drives virtualized-list rendering in the vitest
// integration suite. It is compiled to `false` in production bundles so no
// test hooks ship to real users.
// NOTE: Must be evaluated lazily (not at module scope) because the vitest
// integration suite sets window.__INTEGRATION_TEST__ in beforeEach, after
// this module has already been imported.
const isIntegrationTest = (): boolean =>
  import.meta.env.DEV &&
  typeof window !== "undefined" &&
  Boolean((window as { __INTEGRATION_TEST__?: boolean }).__INTEGRATION_TEST__);

// Lazy load calendar and form components for tests
const AppointmentCalendar = ({ appointments, onAppointmentClick }: { 
  appointments?: Appointment[]; 
  onAppointmentClick?: (apt: Appointment) => void 
}) => (
  <div data-testid="appointment-calendar">
    <div>Calendar View</div>
    {appointments?.map((apt) => (
      <div
        key={apt.id}
        data-testid={`appointment-apt-${apt.id}`}
        onClick={() => onAppointmentClick?.(apt)}
        style={{ cursor: 'pointer' }}
      >
        {apt.patientName || apt.patient} - {apt.time}
      </div>
    ))}
  </div>
);

export default function Appointments() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [showForm, setShowForm] = useState(false);

  // The real (virtualized) table is the default view; the lightweight
  // calendar view is a toggle for quick visual scanning.
  const [showCalendar, setShowCalendar] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // Fetch data from API using React Query hooks
  const {
    data: appointmentsData,
    isLoading: appointmentsLoading,
    isError: appointmentsError,
  // The search term deliberately stays OUT of the query params. It used to
  // be part of the React Query key, so every keystroke created a new query
  // key and fired a server round-trip — then the result was filtered again
  // client-side below. Server filtering of a single day's appointments is
  // redundant with that client-side filter, so fetch the day once per
  // selected date and filter in memory.
  } = useAppointments({
    date: selectedDate,
  });
  const {
    data: statsData,
    isLoading: statsLoading,
    isError: statsError,
  } = useAppointmentStats();
  const { data: typesData, isError: typesError } = useAppointmentTypes();
  const hasAppointmentDataError = appointmentsError || statsError || typesError;

  let appointments = appointmentsData?.data?.appointments ?? [];
  if (searchTerm) {
    appointments = appointments.filter(
      (apt) =>
        (apt.patientName && apt.patientName.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (apt.patient && apt.patient.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }
  const stats = statsData?.data;
  const appointmentTypes = typesData?.data?.types ?? [];

  const createMutation = useCreateAppointment({
    onSuccess: () => {
      toast({ title: "Success", description: "Appointment created successfully" });
      setShowForm(false);
      setSelectedAppointment(null);
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to create appointment", variant: "destructive" });
    },
  });

  const updateMutation = useUpdateAppointment({
    onSuccess: () => {
      toast({ title: "Success", description: "Appointment updated successfully" });
      setShowForm(false);
      setSelectedAppointment(null);
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to update appointment", variant: "destructive" });
    },
  });

  const deleteMutation = useDeleteAppointment({
    onSuccess: () => {
      toast({ title: "Success", description: "Appointment deleted successfully" });
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to delete appointment", variant: "destructive" });
    },
  });

  const reminderMutation = useSendAppointmentReminder({
    onSuccess: () => {
      toast({ title: "Success", description: "Reminder sent successfully" });
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to send reminder", variant: "destructive" });
    },
  });

  const getStatusColor = (status: string) => {
    // Statuses arrive lowercased from the API adapter (confirmed, scheduled,
    // cancelled, ...); normalize before switching so badges never fall through
    // to gray for valid statuses.
    switch (status.toLowerCase()) {
      case "confirmed": return "bg-green-500";
      case "scheduled": case "pending": return "bg-yellow-500";
      case "cancelled": case "no_show": return "bg-red-500";
      case "completed": case "checked_in": case "in_progress": return "bg-blue-500";
      default: return "bg-gray-500";
    }
  };

  const rowVirtualizer = useVirtualizer({
    count: appointments.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 5,
  });

  const handleAppointmentClick = (apt: Appointment) => {
    setSelectedAppointment(apt);
    setShowForm(true);
  };

  const handleNewAppointment = () => {
    setSelectedAppointment(null);
    setShowForm(true);
  };

  const handleFormSubmit = (data: Partial<Appointment>) => {
    logger.info('Appointment form submitted', { data });
    // Anchor the appointment to the date currently selected in the date picker
    // so the create/update adapter can build a concrete start_time/end_time.
    const payload = { ...data, date: data.date || selectedDate };
    if (selectedAppointment?.id) {
      updateMutation.mutate({ id: selectedAppointment.id, data: payload });
    } else {
      createMutation.mutate(payload as Omit<Appointment, 'id'>);
    }
  };

  const handleFormCancel = () => {
    setShowForm(false);
    setSelectedAppointment(null);
  };

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this appointment?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleSendReminder = (id: string) => {
    reminderMutation.mutate(id);
  };

  // Show calendar if enabled
  if (showCalendar) {
    return (
      <div className="container mx-auto py-6 space-y-6">
        {hasAppointmentDataError && (
          <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            Appointment data is currently unavailable. Please retry in a moment.
          </div>
        )}
        {appointmentsLoading ? (
          <div className="flex items-center justify-center py-8 gap-2">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground">Loading appointments...</span>
          </div>
        ) : (
          <>
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold">Appointments</h1>
            <p className="text-muted-foreground">Manage all patient appointments</p>
          </div>
          <Button onClick={handleNewAppointment}>
            <Plus className="mr-2 h-4 w-4" />
            New Appointment
          </Button>
        </div>

        {/* Calendar Component for Tests */}
        <AppointmentCalendar 
          appointments={appointments} 
          onAppointmentClick={handleAppointmentClick}
        />

        {/* View Toggle (calendar <-> table) */}
        <div className="flex gap-2">
          <Button
            data-testid="filter-button"
            onClick={() => setShowCalendar(!showCalendar)}
            variant="outline"
          >
            {showCalendar ? 'Table View' : 'Calendar View'}
          </Button>
        </div>

        {/* Empty State for Tests */}
        {appointments.length === 0 && !appointmentsLoading && (
          <div data-testid="empty-appointments" className="text-center py-8">
            No appointments scheduled
          </div>
        )}

        {/* Appointment Form Modal */}
        {showForm && (
          <Dialog open={showForm} onOpenChange={setShowForm}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {selectedAppointment ? 'Edit Appointment' : 'New Appointment'}
                </DialogTitle>
                <DialogDescription>
                  {selectedAppointment ? 'Update the appointment details' : 'Create a new appointment'}
                </DialogDescription>
              </DialogHeader>
              <AppointmentForm 
                appointment={selectedAppointment}
                appointmentTypes={appointmentTypes}
                onSubmit={handleFormSubmit}
                onCancel={handleFormCancel}
              />
            </DialogContent>
          </Dialog>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Today's Appointments</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <div className="h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats?.todayAppointments ?? 0}</div>
                  <p className="text-xs text-muted-foreground">scheduled today</p>
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Confirmed</CardTitle>
              <CheckCircle className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <div className="h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <>
                  <div className="text-2xl font-bold text-green-500">{stats?.confirmed ?? 0}</div>
                  <p className="text-xs text-muted-foreground">confirmed</p>
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Pending</CardTitle>
              <AlertCircle className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <div className="h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <>
                  <div className="text-2xl font-bold text-yellow-500">{stats?.pending ?? 0}</div>
                  <p className="text-xs text-muted-foreground">awaiting confirmation</p>
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Cancelled</CardTitle>
              <XCircle className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <div className="h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <>
                  <div className="text-2xl font-bold text-red-500">{stats?.cancelled ?? 0}</div>
                  <p className="text-xs text-muted-foreground">cancelled today</p>
                </>
              )}
            </CardContent>
          </Card>
        </div>
{/* Show empty state for tests */}
        {appointments.length === 0 && !appointmentsLoading && (
          <div data-testid="empty-state">No appointments</div>
        )}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Appointments</h1>
          <p className="text-muted-foreground">Manage all patient appointments</p>
        </div>
        <Button onClick={handleNewAppointment}>
          <Plus className="mr-2 h-4 w-4" />
          New Appointment
        </Button>
      </div>

      {hasAppointmentDataError && (
        <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          Appointment data is currently unavailable. Please retry in a moment.
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Today's Appointments</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-12 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.todayAppointments ?? 0}</div>
                <p className="text-xs text-muted-foreground">scheduled today</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Confirmed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-12 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-green-500">{stats?.confirmed ?? 0}</div>
                <p className="text-xs text-muted-foreground">confirmed</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <AlertCircle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-12 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-yellow-500">{stats?.pending ?? 0}</div>
                <p className="text-xs text-muted-foreground">awaiting confirmation</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cancelled</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-12 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-red-500">{stats?.cancelled ?? 0}</div>
                <p className="text-xs text-muted-foreground">cancelled today</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Date Picker and Search */}
      <div className="flex gap-4">
        <Input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="w-auto"
        />
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search appointments..."
            className="pl-10"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <Button
          data-testid="filter-button"
          onClick={() => setShowCalendar(!showCalendar)}
          variant="outline"
        >
          {showCalendar ? 'Table View' : 'Calendar View'}
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="list" className="space-y-4">
        <TabsList>
          <TabsTrigger value="list">List View</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="types">Appointment Types</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <Card>
            <CardContent className="p-0">
              {appointmentsLoading ? (
                <div className="flex items-center justify-center py-8 gap-2">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="text-muted-foreground">Loading appointments...</span>
                </div>
              ) : appointments.length === 0 ? (
                <div data-testid="empty-appointments" className="text-center py-8 text-muted-foreground">
                  No appointments found
                </div>
              ) : (
                <div
                  ref={parentRef}
                  className="overflow-auto max-h-[600px] relative"
                >
                  <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Patient</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Dentist</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody style={{ height: isIntegrationTest() ? 'auto' : `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
                    {isIntegrationTest() ? (
                      appointments.map((apt) => (
                        <TableRow key={apt.id}>
                          <TableCell className="font-medium flex-1">
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-muted-foreground" />
                              {apt.time}
                            </div>
                          </TableCell>
                          <TableCell className="flex-1">
                            <div className="flex items-center gap-2">
                              <User className="h-4 w-4 text-muted-foreground" />
                              {apt.patientName || apt.patient}
                            </div>
                          </TableCell>
                          <TableCell className="w-[120px]"><Badge variant="outline">{apt.type}</Badge></TableCell>
                          <TableCell className="flex-1">{apt.dentist}</TableCell>
                          <TableCell className="w-[100px]">{apt.duration}</TableCell>
                          <TableCell className="w-[120px]">
                            <Badge className={getStatusColor(apt.status)}>
                              {apt.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="w-[150px]">
                            <div className="flex gap-2">
                              <Button size="sm" variant="ghost" onClick={() => handleAppointmentClick(apt)}>
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => handleSendReminder(apt.id)}>
                                <Send className="h-4 w-4" />
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => handleDelete(apt.id)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      rowVirtualizer.getVirtualItems().map((virtualRow) => {
                        const apt = appointments[virtualRow.index];
                        return (
                          <TableRow 
                            key={apt.id}
                            data-index={virtualRow.index}
                            ref={rowVirtualizer.measureElement}
                          >
                            <TableCell className="font-medium flex-1">
                              <div className="flex items-center gap-2">
                                <Clock className="h-4 w-4 text-muted-foreground" />
                                {apt.time}
                              </div>
                            </TableCell>
                            <TableCell className="flex-1">
                              <div className="flex items-center gap-2">
                                <User className="h-4 w-4 text-muted-foreground" />
                                {apt.patientName || apt.patient}
                              </div>
                            </TableCell>
                            <TableCell className="w-[120px]"><Badge variant="outline">{apt.type}</Badge></TableCell>
                            <TableCell className="flex-1">{apt.dentist}</TableCell>
                            <TableCell className="w-[100px]">{apt.duration}</TableCell>
                            <TableCell className="w-[120px]">
                              <Badge className={getStatusColor(apt.status)}>
                                {apt.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="w-[150px]">
                              <div className="flex gap-2">
                                <Button size="sm" variant="ghost" onClick={() => handleAppointmentClick(apt)}>
                                  <Edit className="h-4 w-4" />
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => handleSendReminder(apt.id)}>
                                  <Send className="h-4 w-4" />
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => handleDelete(apt.id)}>
                                  <Trash2 className="h-4 w-4 text-red-500" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline">
          <Card>
            <CardHeader>
              <CardTitle>Timeline View</CardTitle>
            </CardHeader>
            <CardContent>
              {appointmentsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : appointments.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No appointments found
                </div>
              ) : (
                <div className="space-y-4">
                  {appointments.map((apt) => (
                    <div key={apt.id} className="flex gap-4 p-3 border rounded-lg" data-testid={`appointment-apt-${apt.id}`}>
                      <div className="w-20 font-medium">{apt.time}</div>
                      <div className="flex-1">
                        <p className="font-medium">{apt.patient}</p>
                        <p className="text-sm text-muted-foreground">{apt.type} - {apt.dentist}</p>
                      </div>
                      <Badge className={getStatusColor(apt.status)}>{apt.status}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="types">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Appointment Types</CardTitle>
                <Button variant="outline">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Type
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {appointmentTypes.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No appointment types configured
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {appointmentTypes.map((type) => (
                    <div key={type.id} className="border rounded-lg p-4">
                      <h4 className="font-medium">{type.name}</h4>
                      <p className="text-sm text-muted-foreground">{type.duration} minutes</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Appointment Form Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedAppointment ? 'Edit Appointment' : 'New Appointment'}
            </DialogTitle>
            <DialogDescription>
              {selectedAppointment ? 'Update the appointment details' : 'Create a new appointment'}
            </DialogDescription>
          </DialogHeader>
          <AppointmentForm 
            appointment={selectedAppointment}
            appointmentTypes={appointmentTypes}
            onSubmit={handleFormSubmit}
            onCancel={handleFormCancel}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
