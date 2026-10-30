// ============================================
// Patient List Page
// Main patient directory with search and filters
// ============================================

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import {
  MoreHorizontal,
  Phone,
  Mail,
  Calendar,
  AlertTriangle,
  User,
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { format, differenceInYears, parseISO } from 'date-fns';
import { useAuth } from '@/contexts/auth-context';
import { patientApi } from '@/services/patientApi';
import { PatientDialog } from '@/components/patients/PatientDialog';
import type { PatientListItem, PatientSearchParams } from '@/types/patient';

import { useVirtualizer } from '@tanstack/react-virtual';

// The backend caps list requests at 100 records per page (deps.py clamp), so
// page through the directory instead of requesting more than it can return.
const PAGE_SIZE = 100;

export default function PatientList() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const parentRef = useRef<HTMLDivElement>(null);

  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [totalPatients, setTotalPatients] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('active');
  const [page, setPage] = useState(1);

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  // Load patients
  const loadPatients = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: PatientSearchParams = {
        query: searchQuery || undefined,
        // "All" is omitted rather than sent: the API filters status == the given
        // value and no patient carries the status "all", so the default filter
        // returned an empty directory that looked like a practice with no
        // patients.
        status: statusFilter === 'all' ? undefined : statusFilter,
        page,
        limit: PAGE_SIZE,
      };
      const result = await patientApi.getPatients(params);
      setPatients(result.data);
      setTotalPatients(result.total);
      setTotalPages(result.totalPages || Math.max(1, Math.ceil(result.total / PAGE_SIZE)));
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to load patients',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, statusFilter, page, toast]);

  // Load once on mount and debounce subsequent filter/search changes.
  // NOTE: this single effect intentionally replaces the previous pair
  // (an immediate effect on [loadPatients] PLUS a debounced effect on
  // [searchQuery, loadPatients]) that fired two requests per change.
  useEffect(() => {
    const timer = setTimeout(() => {
      loadPatients();
    }, 300);
    return () => clearTimeout(timer);
  }, [loadPatients]);

  // A new search term or status filter always restarts from the first page.
  useEffect(() => {
    setPage(1);
  }, [searchQuery, statusFilter]);

  const rowVirtualizer = useVirtualizer({
    count: patients.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 5,
  });

  const handleStatusFilterChange = (value: string) => {
    if (value === 'all' || value === 'active' || value === 'inactive') {
      setStatusFilter(value);
    }
  };

  const handleViewPatient = (id: string) => {
    navigate(`/patients/${id}`);
  };

  const handlePatientCreated = () => {
    setIsCreateDialogOpen(false);
    loadPatients();
    toast({
      title: 'Patient Created',
      description: 'New patient record has been created',
    });
  };

  const calculateAge = (dob: string) => {
    return differenceInYears(new Date(), parseISO(dob));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Patients</h1>
          <p className="text-muted-foreground">
            {totalPatients} patient{totalPatients !== 1 ? 's' : ''} in directory
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Patient
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, phone, or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        
        <div className="flex gap-2">
          <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Patient Table - Virtualized */}
      <div 
        ref={parentRef}
        className="border rounded-lg bg-card overflow-auto max-h-[700px] relative scrollbar-thin"
      >
        <Table className="table-fixed w-full">
          <TableHeader className="sticky top-0 bg-card z-20 shadow-sm border-b">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[300px]">Patient</TableHead>
              <TableHead className="w-[220px]">Contact</TableHead>
              <TableHead className="w-[80px]">Age</TableHead>
              <TableHead className="w-[140px]">Last Visit</TableHead>
              <TableHead className="w-[140px]">Next Appt</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[60px] text-right"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody 
            className="relative"
            style={{ 
              height: `${rowVirtualizer.getTotalSize()}px`,
            }}
          >
            {isLoading ? (
              Array.from({ length: 10 }).map((_, i) => (
                <TableRow key={i} className="absolute w-full" style={{ top: i * 72 }}>
                  <TableCell className="w-[300px]"><Skeleton className="h-10 w-48" /></TableCell>
                  <TableCell className="w-[220px]"><Skeleton className="h-10 w-40" /></TableCell>
                  <TableCell className="w-[80px]"><Skeleton className="h-6 w-12" /></TableCell>
                  <TableCell className="w-[140px]"><Skeleton className="h-6 w-24" /></TableCell>
                  <TableCell className="w-[140px]"><Skeleton className="h-6 w-24" /></TableCell>
                  <TableCell className="w-[100px]"><Skeleton className="h-6 w-16" /></TableCell>
                  <TableCell className="w-[60px]"><Skeleton className="h-8 w-8 ml-auto" /></TableCell>
                </TableRow>
              ))
            ) : patients.length === 0 ? (
              <TableRow className="absolute w-full h-[300px]">
                <TableCell colSpan={7} className="h-full text-center">
                  <div className="flex flex-col items-center justify-center text-muted-foreground w-full h-full">
                    <User className="h-12 w-12 mb-2 opacity-30" />
                    <p>No patients found</p>
                    <p className="text-sm">Try adjusting your search or filters</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const patient = patients[virtualRow.index];
                if (!patient) return null;

                return (
                  <TableRow 
                    key={patient.id}
                    data-index={virtualRow.index}
                    ref={rowVirtualizer.measureElement}
                    className="cursor-pointer hover:bg-muted/50 absolute top-0 left-0 w-full flex items-center"
                    style={{ 
                      transform: `translateY(${virtualRow.start}px)`,
                      height: `${virtualRow.size}px`
                    }}
                    onClick={() => handleViewPatient(patient.id)}
                  >
                    <TableCell className="w-[300px]">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                          <span className="text-xs font-bold text-primary">
                            {patient.firstName[0]}{patient.lastName[0]}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold truncate flex items-center gap-2">
                            {patient.firstName} {patient.lastName}
                            {patient.hasMedicalAlerts && (
                              <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />
                            )}
                          </div>
                          {patient.hasMedicalAlerts && (
                            <div className="text-xs text-destructive truncate">
                              {patient.medicalAlerts.join(', ')}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="w-[220px]">
                      <div className="text-sm space-y-0.5">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Phone className="h-3.5 w-3.5" />
                          {patient.phone}
                        </div>
                        <div className="flex items-center gap-1.5 text-muted-foreground truncate">
                          <Mail className="h-3.5 w-3.5" />
                          <span className="truncate">{patient.email}</span>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="w-[80px]">
                      <span className="text-sm font-medium">{calculateAge(patient.dateOfBirth)}</span>
                    </TableCell>
                    <TableCell className="w-[140px]">
                      {patient.lastVisit ? (
                        <span className="text-sm">
                          {format(parseISO(patient.lastVisit), 'MMM d, yyyy')}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">Never</span>
                      )}
                    </TableCell>
                    <TableCell className="w-[140px]">
                      {patient.nextAppointment ? (
                        <div className="flex items-center gap-1.5 text-sm font-medium text-primary">
                          <Calendar className="h-4 w-4" />
                          {format(parseISO(patient.nextAppointment), 'MMM d')}
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="w-[100px]">
                      <Badge variant={patient.status === 'active' ? 'default' : 'secondary'} className="capitalize">
                        {patient.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="w-[60px] text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleViewPatient(patient.id); }}>
                            <User className="h-4 w-4 mr-2" />
                            View Profile
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); navigate('/schedule'); }}>
                            <Calendar className="h-4 w-4 mr-2" />
                            Schedule
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); window.location.href = `tel:${patient.phone}`; }}>
                            <Phone className="h-4 w-4 mr-2" />
                            Call
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between" data-testid="patient-list-pagination">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            disabled={page <= 1 || isLoading}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={page >= totalPages || isLoading}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>

      {/* Create Patient Dialog */}
      <PatientDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onSave={handlePatientCreated}
        region={user?.practiceCountry || 'US'}
      />
    </div>
  );
}
