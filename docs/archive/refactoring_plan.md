# 🧹 CoreDent PMS - Refactoring Plan

**Date:** March 13, 2026  
**Objective:** Improve code maintainability, reduce technical debt  
**Estimated Effort:** 4-6 weeks

---

## Executive Summary

This refactoring plan addresses code quality issues identified in the audit. The focus is on splitting large components, extracting reusable logic, and establishing consistent patterns.

**Priority:** HIGH (Technical debt will compound)  
**Impact:** Improved maintainability, faster feature development

---

## 1. Component Splitting Strategy

### Phase 1: Split Oversized Components (Week 1-2)

#### R-001: Reports.tsx (646 lines → 6 files)

**Current Structure:**
```
Reports.tsx (646 lines)
├── State management (50 lines)
├── Data fetching (100 lines)
├── Date range picker (80 lines)
├── Metrics cards (100 lines)
├── Charts (200 lines)
└── Export logic (116 lines)
```

**Target Structure:**
```
pages/Reports/
├── index.tsx (100 lines) - Container
├── ReportsHeader.tsx (60 lines) - Filters & date picker
├── MetricsOverview.tsx (80 lines) - KPI cards
├── ProductionChart.tsx (70 lines)
├── AppointmentChart.tsx (70 lines)
├── RevenueChart.tsx (70 lines)
└── hooks/
    ├── useReportsData.ts (80 lines)
    ├── useReportsFilters.ts (50 lines)
    └── useReportsExport.ts (40 lines)
```

**Implementation:**

```typescript
// pages/Reports/index.tsx
import { ReportsHeader } from './ReportsHeader';
import { MetricsOverview } from './MetricsOverview';
import { ProductionChart } from './ProductionChart';
import { useReportsData } from './hooks/useReportsData';
import { useReportsFilters } from './hooks/useReportsFilters';

export default function Reports() {
  const { dateRange, preset, setDateRange, setPreset } = useReportsFilters();
  const { metrics, isLoading } = useReportsData(dateRange);
  
  return (
    <div className="space-y-6">
      <ReportsHeader
        dateRange={dateRange}
        preset={preset}
        onDateRangeChange={setDateRange}
        onPresetChange={setPreset}
      />
      
      <MetricsOverview metrics={metrics} isLoading={isLoading} />
      
      <div className="grid grid-cols-2 gap-6">
        <ProductionChart data={metrics?.production} />
        <AppointmentChart data={metrics?.appointments} />
      </div>
    </div>
  );
}
```

```typescript
// pages/Reports/hooks/useReportsData.ts
import { useQuery } from '@tanstack/react-query';
import { reportsApi } from '@/services/reportsApi';

export function useReportsData(dateRange: DateRange) {
  return useQuery({
    queryKey: ['reports', 'dashboard', dateRange],
    queryFn: () => reportsApi.getDashboardMetrics(dateRange),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

**Effort:** 8 hours  
**Priority:** HIGH

---

#### R-002: PatientProfile.tsx (646 lines → 8 files)

**Target Structure:**
```
pages/patients/PatientProfile/
├── index.tsx (80 lines) - Container
├── PatientHeader.tsx (60 lines)
├── PatientInfo.tsx (80 lines)
├── AppointmentHistory.tsx (100 lines)
├── TreatmentHistory.tsx (100 lines)
├── BillingHistory.tsx (100 lines)
├── DocumentsList.tsx (80 lines)
└── hooks/
    └── usePatientData.ts (60 lines)
```

**Effort:** 8 hours  
**Priority:** HIGH

---

#### R-003: StaffSettingsTab.tsx (577 lines → 5 files)

**Target Structure:**
```
components/settings/StaffSettings/
├── index.tsx (80 lines)
├── StaffList.tsx (120 lines)
├── StaffDialog.tsx (150 lines)
├── InviteStaffDialog.tsx (120 lines)
└── hooks/
    └── useStaffManagement.ts (100 lines)
```

**Effort:** 6 hours  
**Priority:** MEDIUM

---

### Phase 2: Extract Reusable Components (Week 2-3)

#### R-004: Create DataTable Component

**Problem:** Table logic duplicated across 10+ components.

**Solution:**
```typescript
// components/ui/DataTable.tsx
interface Column<T> {
  key: keyof T;
  header: string;
  render?: (value: any, row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function DataTable<T extends { id: string }>({
  data,
  columns,
  isLoading,
  onRowClick,
  emptyMessage = 'No data available',
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  
  const sortedData = useMemo(() => {
    if (!sortKey) return data;
    
    return [...data].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      
      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortKey, sortOrder]);
  
  if (isLoading) {
    return <TableSkeleton />;
  }
  
  if (data.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }
  
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((column) => (
            <TableHead
              key={String(column.key)}
              style={{ width: column.width }}
              onClick={() => column.sortable && handleSort(column.key)}
            >
              {column.header}
              {column.sortable && <SortIcon />}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedData.map((row) => (
          <TableRow
            key={row.id}
            onClick={() => onRowClick?.(row)}
            className={onRowClick ? 'cursor-pointer hover:bg-muted' : ''}
          >
            {columns.map((column) => (
              <TableCell key={String(column.key)}>
                {column.render
                  ? column.render(row[column.key], row)
                  : String(row[column.key])}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

**Usage:**
```typescript
// Before: 50 lines of table code
// After:
<DataTable
  data={patients}
  columns={[
    { key: 'name', header: 'Name', sortable: true },
    { key: 'email', header: 'Email' },
    { key: 'phone', header: 'Phone' },
    {
      key: 'status',
      header: 'Status',
      render: (status) => <StatusBadge status={status} />,
    },
  ]}
  onRowClick={(patient) => navigate(`/patients/${patient.id}`)}
/>
```

**Effort:** 6 hours  
**Impact:** Eliminates 500+ lines of duplicated code

---

#### R-005: Create FormField Component

**Problem:** Form field patterns repeated 50+ times.

**Solution:**
```typescript
// components/ui/FormField.tsx
interface FormFieldProps {
  name: string;
  label: string;
  type?: 'text' | 'email' | 'tel' | 'number' | 'textarea' | 'select';
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  error?: string;
  helperText?: string;
}

export function FormField({
  name,
  label,
  type = 'text',
  placeholder,
  required,
  options,
  error,
  helperText,
}: FormFieldProps) {
  const { register, formState } = useFormContext();
  
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      
      {type === 'textarea' ? (
        <Textarea
          id={name}
          placeholder={placeholder}
          {...register(name)}
          aria-invalid={!!error}
          aria-describedby={error ? `${name}-error` : undefined}
        />
      ) : type === 'select' ? (
        <Select {...register(name)}>
          <SelectTrigger>
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options?.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <Input
          id={name}
          type={type}
          placeholder={placeholder}
          {...register(name)}
          aria-invalid={!!error}
          aria-describedby={error ? `${name}-error` : undefined}
        />
      )}
      
      {helperText && !error && (
        <p className="text-sm text-muted-foreground">{helperText}</p>
      )}
      
      {error && (
        <p id={`${name}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
```

**Usage:**
```typescript
// Before: 15 lines per field
<div>
  <Label htmlFor="email">Email</Label>
  <Input
    id="email"
    type="email"
    {...register('email')}
  />
  {errors.email && <p>{errors.email.message}</p>}
</div>

// After: 1 line per field
<FormField
  name="email"
  label="Email"
  type="email"
  required
  error={errors.email?.message}
/>
```

**Effort:** 4 hours  
**Impact:** Eliminates 300+ lines of duplicated code

---

#### R-006: Create LoadingState Component

**Problem:** Loading skeletons duplicated 20+ times.

**Solution:**
```typescript
// components/ui/LoadingState.tsx
type LoadingVariant = 'table' | 'card' | 'list' | 'form' | 'chart';

interface LoadingStateProps {
  variant: LoadingVariant;
  count?: number;
}

export function LoadingState({ variant, count = 3 }: LoadingStateProps) {
  switch (variant) {
    case 'table':
      return <TableSkeleton rows={count} />;
    case 'card':
      return <CardSkeleton count={count} />;
    case 'list':
      return <ListSkeleton items={count} />;
    case 'form':
      return <FormSkeleton fields={count} />;
    case 'chart':
      return <ChartSkeleton />;
  }
}
```

**Effort:** 3 hours

---

#### R-007: Create EmptyState Component

**Problem:** Empty state UI duplicated 15+ times.

**Solution:**
```typescript
// components/ui/EmptyState.tsx
interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  icon: Icon = FileQuestion,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icon className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground mt-2 max-w-sm">
          {description}
        </p>
      )}
      {action && (
        <Button onClick={action.onClick} className="mt-4">
          {action.label}
        </Button>
      )}
    </div>
  );
}
```

**Effort:** 2 hours

---

## 2. Custom Hooks Extraction (Week 3-4)

### R-008: useApiMutation Hook

**Problem:** API call patterns repeated 40+ times.

**Solution:**
```typescript
// hooks/useApiMutation.ts
interface UseApiMutationOptions<TData, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData>;
  onSuccess?: (data: TData) => void;
  onError?: (error: Error) => void;
  successMessage?: string;
  errorMessage?: string;
}

export function useApiMutation<TData = unknown, TVariables = void>({
  mutationFn,
  onSuccess,
  onError,
  successMessage,
  errorMessage,
}: UseApiMutationOptions<TData, TVariables>) {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (successMessage) {
        toast({
          title: 'Success',
          description: successMessage,
        });
      }
      onSuccess?.(data);
    },
    onError: (error: Error) => {
      logger.error('Mutation failed', error);
      toast({
        variant: 'destructive',
        title: 'Error',
        description: errorMessage || error.message,
      });
      onError?.(error);
    },
  });
}
```

**Usage:**
```typescript
// Before: 20 lines
const [isLoading, setIsLoading] = useState(false);

const handleSave = async () => {
  setIsLoading(true);
  try {
    await patientApi.create(data);
    toast({ title: 'Success' });
    onSuccess();
  } catch (error) {
    toast({ variant: 'destructive', title: 'Error' });
  } finally {
    setIsLoading(false);
  }
};

// After: 5 lines
const { mutate, isPending } = useApiMutation({
  mutationFn: patientApi.create,
  successMessage: 'Patient created successfully',
  onSuccess,
});
```

**Effort:** 4 hours  
**Impact:** Eliminates 600+ lines of boilerplate

---

### R-009: usePagination Hook

**Solution:**
```typescript
// hooks/usePagination.ts
export function usePagination(totalItems: number, itemsPerPage: number = 10) {
  const [currentPage, setCurrentPage] = useState(1);
  
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  
  const goToPage = (page: number) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };
  
  const nextPage = () => goToPage(currentPage + 1);
  const prevPage = () => goToPage(currentPage - 1);
  
  return {
    currentPage,
    totalPages,
    startIndex,
    endIndex,
    goToPage,
    nextPage,
    prevPage,
    hasNextPage: currentPage < totalPages,
    hasPrevPage: currentPage > 1,
  };
}
```

**Effort:** 2 hours

---

### R-010: useDebounce Hook

**Already covered in performance_optimization.md**

---

### R-011: useLocalStorage Hook

**Solution:**
```typescript
// hooks/useLocalStorage.ts
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T) => void, () => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      logger.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });
  
  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      logger.error(`Error setting localStorage key "${key}":`, error);
    }
  };
  
  const removeValue = () => {
    try {
      window.localStorage.removeItem(key);
      setStoredValue(initialValue);
    } catch (error) {
      logger.error(`Error removing localStorage key "${key}":`, error);
    }
  };
  
  return [storedValue, setValue, removeValue];
}
```

**Effort:** 2 hours

---

### R-012: usePermissions Hook

**Solution:**
```typescript
// hooks/usePermissions.ts
export function usePermissions() {
  const { user } = useAuth();
  
  const can = useCallback((permission: Permission): boolean => {
    if (!user) return false;
    
    const rolePermissions: Record<UserRole, Permission[]> = {
      owner: ['*'],
      admin: ['read', 'write', 'delete', 'manage_staff'],
      dentist: ['read', 'write', 'view_clinical'],
      hygienist: ['read', 'write_limited', 'view_clinical'],
      receptionist: ['read', 'schedule', 'billing'],
    };
    
    const permissions = rolePermissions[user.role];
    return permissions.includes('*') || permissions.includes(permission);
  }, [user]);
  
  const canAny = useCallback((permissions: Permission[]): boolean => {
    return permissions.some(can);
  }, [can]);
  
  const canAll = useCallback((permissions: Permission[]): boolean => {
    return permissions.every(can);
  }, [can]);
  
  return { can, canAny, canAll };
}
```

**Usage:**
```typescript
function PatientActions() {
  const { can } = usePermissions();
  
  return (
    <>
      {can('write') && <Button>Edit</Button>}
      {can('delete') && <Button variant="destructive">Delete</Button>}
    </>
  );
}
```

**Effort:** 3 hours

---

## 3. Service Layer Refactoring (Week 4)

### R-013: Extract Business Logic from Components

**Problem:** Business logic mixed with UI logic.

**Solution:**
```typescript
// services/patientService.ts
export class PatientService {
  constructor(private api: typeof patientApi) {}
  
  async createPatient(data: PatientFormData): Promise<Patient> {
    // Validation
    this.validatePatientData(data);
    
    // Transform data
    const patientData = this.transformPatientData(data);
    
    // API call
    const response = await this.api.create(patientData);
    
    // Post-processing
    return this.enrichPatientData(response.data);
  }
  
  private validatePatientData(data: PatientFormData): void {
    if (!isValidEmail(data.email)) {
      throw new Error('Invalid email format');
    }
    
    if (!isValidPhone(data.phone)) {
      throw new Error('Invalid phone format');
    }
  }
  
  private transformPatientData(data: PatientFormData): PatientCreate {
    return {
      ...data,
      phone: this.formatPhone(data.phone),
      dateOfBirth: this.formatDate(data.dateOfBirth),
    };
  }
  
  private enrichPatientData(patient: Patient): Patient {
    return {
      ...patient,
      fullName: `${patient.firstName} ${patient.lastName}`,
      age: this.calculateAge(patient.dateOfBirth),
    };
  }
  
  private formatPhone(phone: string): string {
    return phone.replace(/\D/g, '');
  }
  
  private formatDate(date: Date): string {
    return format(date, 'yyyy-MM-dd');
  }
  
  private calculateAge(dateOfBirth: string): number {
    const today = new Date();
    const birthDate = new Date(dateOfBirth);
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    
    return age;
  }
}

export const patientService = new PatientService(patientApi);
```

**Usage in Component:**
```typescript
// Before: 50 lines of logic in component
function PatientDialog() {
  const handleSubmit = async (data) => {
    // 50 lines of validation, transformation, API calls
  };
}

// After: Clean component
function PatientDialog() {
  const { mutate } = useApiMutation({
    mutationFn: patientService.createPatient,
    successMessage: 'Patient created',
  });
  
  const handleSubmit = (data: PatientFormData) => {
    mutate(data);
  };
}
```

**Effort:** 12 hours  
**Impact:** Testable business logic, reusable across components

---

## 4. Code Organization (Week 5)

### R-014: Establish Consistent File Structure

**Current Issues:**
- Inconsistent naming (some PascalCase, some kebab-case)
- Mixed file locations
- No clear pattern

**Target Structure:**
```
src/
├── components/
│   ├── ui/              # Reusable UI components
│   ├── layout/          # Layout components
│   ├── patients/        # Feature-specific components
│   ├── appointments/
│   └── billing/
├── pages/               # Route components
│   ├── Dashboard/
│   ├── patients/
│   │   ├── PatientList/
│   │   └── PatientProfile/
│   └── Reports/
├── hooks/               # Shared custom hooks
├── services/            # API clients & business logic
├── lib/                 # Utilities
├── types/               # TypeScript types
└── contexts/            # React contexts
```

**Naming Conventions:**
- Components: PascalCase (PatientCard.tsx)
- Hooks: camelCase with 'use' prefix (usePatientData.ts)
- Services: camelCase (patientService.ts)
- Types: PascalCase (Patient.ts)
- Utils: camelCase (formatDate.ts)

**Effort:** 8 hours

---

## 5. Testing Strategy (Week 6)

### R-015: Add Unit Tests for Business Logic

**Target Coverage:** 80%

**Priority Tests:**
```typescript
// services/__tests__/patientService.test.ts
describe('PatientService', () => {
  describe('createPatient', () => {
    it('should validate email format', () => {
      expect(() => {
        patientService.validatePatientData({
          email: 'invalid-email',
        });
      }).toThrow('Invalid email format');
    });
    
    it('should format phone number', () => {
      const result = patientService.formatPhone('(555) 123-4567');
      expect(result).toBe('5551234567');
    });
    
    it('should calculate age correctly', () => {
      const age = patientService.calculateAge('1990-01-01');
      expect(age).toBe(36);
    });
  });
});
```

**Effort:** 16 hours

---

## 6. Documentation (Week 6)

### R-016: Add Component Documentation

**Use JSDoc:**
```typescript
/**
 * DataTable component for displaying tabular data with sorting and filtering.
 * 
 * @example
 * ```tsx
 * <DataTable
 *   data={patients}
 *   columns={[
 *     { key: 'name', header: 'Name', sortable: true },
 *     { key: 'email', header: 'Email' },
 *   ]}
 *   onRowClick={(patient) => navigate(`/patients/${patient.id}`)}
 * />
 * ```
 * 
 * @param data - Array of data objects to display
 * @param columns - Column configuration
 * @param isLoading - Show loading skeleton
 * @param onRowClick - Callback when row is clicked
 */
export function DataTable<T>({ ... }) { ... }
```

**Effort:** 8 hours

---

## Implementation Timeline

### Week 1-2: Component Splitting
- [ ] Split Reports.tsx
- [ ] Split PatientProfile.tsx
- [ ] Split StaffSettingsTab.tsx

### Week 2-3: Reusable Components
- [ ] Create DataTable
- [ ] Create FormField
- [ ] Create LoadingState
- [ ] Create EmptyState

### Week 3-4: Custom Hooks
- [ ] useApiMutation
- [ ] usePagination
- [ ] useLocalStorage
- [ ] usePermissions

### Week 4: Service Layer
- [ ] Extract PatientService
- [ ] Extract AppointmentService
- [ ] Extract BillingService

### Week 5: Organization
- [ ] Reorganize file structure
- [ ] Establish naming conventions
- [ ] Update imports

### Week 6: Testing & Docs
- [ ] Add unit tests
- [ ] Add component documentation
- [ ] Update README

---

## Success Metrics

### Before Refactoring
- Average component size: 250 lines
- Code duplication: ~30%
- Test coverage: ~40%
- Time to add feature: 2-3 days

### After Refactoring
- Average component size: 100 lines
- Code duplication: <10%
- Test coverage: >80%
- Time to add feature: 1 day

---

## Estimated Effort

| Phase | Tasks | Hours | Priority |
|-------|-------|-------|----------|
| Component Splitting | 3 components | 22h | HIGH |
| Reusable Components | 4 components | 15h | HIGH |
| Custom Hooks | 4 hooks | 11h | MEDIUM |
| Service Layer | 3 services | 12h | MEDIUM |
| Organization | File structure | 8h | LOW |
| Testing & Docs | Tests + docs | 24h | MEDIUM |
| **Total** | | **92h** | **~4-6 weeks** |

---

**End of Refactoring Plan**
