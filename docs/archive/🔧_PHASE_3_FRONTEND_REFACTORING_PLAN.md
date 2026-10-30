# 🔧 PHASE 3: FRONTEND COMPONENTS REFACTORING PLAN

**Status**: ⏳ IN PROGRESS  
**Date**: April 10, 2026  
**Estimated Duration**: 8 hours  
**Project Progress**: 17/29 hours (59%)

---

## PHASE 3 OBJECTIVES

1. **Identify Large Components** - Find components >300 lines
2. **Extract Custom Hooks** - Move logic into reusable hooks
3. **Optimize Performance** - Implement memoization and lazy loading
4. **Refactor Components** - Split into smaller, focused components
5. **Improve Maintainability** - Better code organization and readability

---

## COMPONENTS IDENTIFIED FOR REFACTORING

### Priority 1: Large Page Components (400+ lines)

#### 1. Dashboard.tsx (400+ lines)
**Current Issues**:
- Multiple data fetching queries mixed with rendering logic
- Complex state calculations (useMemo chains)
- Inline component definitions (ActivityItem)
- Mixed concerns: metrics, appointments, billing

**Refactoring Strategy**:
- Extract `useDashboardMetrics()` hook
- Extract `useTodayAppointments()` hook
- Extract `useBillingSummary()` hook
- Extract `ActivityItem` component
- Extract `StatCard` component
- Extract `ScheduleCard` component
- Extract `ActivityCard` component

**Target**: 400 → 150 lines (62% reduction)

#### 2. Appointments.tsx (300+ lines)
**Current Issues**:
- Calendar and form logic mixed
- Multiple state management concerns
- Inline component definitions

**Refactoring Strategy**:
- Extract `useAppointmentCalendar()` hook
- Extract `useAppointmentForm()` hook
- Extract `AppointmentCalendar` component
- Extract `AppointmentForm` component

**Target**: 300 → 120 lines (60% reduction)

### Priority 2: Complex Components (200-300 lines)

#### 3. TreatmentPlanDialog.tsx (200+ lines)
**Current Issues**:
- Form logic mixed with dialog logic
- Validation schema inline
- Multiple form fields

**Refactoring Strategy**:
- Extract `useTreatmentPlanForm()` hook
- Extract form schema to separate file
- Extract form fields to separate components

**Target**: 200 → 100 lines (50% reduction)

#### 4. PatientMedicalTab.tsx (200+ lines)
**Current Issues**:
- Multiple data fetching queries
- Complex filtering and sorting logic
- Mixed concerns

**Refactoring Strategy**:
- Extract `usePatientMedicalData()` hook
- Extract filtering logic to utility functions
- Extract sub-components

**Target**: 200 → 100 lines (50% reduction)

### Priority 3: Utility Components (100-200 lines)

#### 5. VirtualizedPatientList.tsx (100+ lines)
**Current Issues**:
- Virtualization logic mixed with rendering
- Could benefit from custom hook

**Refactoring Strategy**:
- Extract `useVirtualizedList()` hook
- Simplify component to focus on rendering

**Target**: 100 → 60 lines (40% reduction)

---

## CUSTOM HOOKS TO CREATE

### Data Fetching Hooks

1. **useDashboardMetrics()**
   - Fetches dashboard metrics
   - Handles loading/error states
   - Caches results

2. **useTodayAppointments()**
   - Fetches today's appointments
   - Filters and sorts appointments
   - Calculates statistics

3. **useBillingSummary()**
   - Fetches billing summary
   - Calculates pending amounts
   - Handles currency formatting

4. **usePatientMedicalData()**
   - Fetches patient medical records
   - Handles filtering and sorting
   - Manages pagination

5. **useAppointmentCalendar()**
   - Manages calendar state
   - Handles date navigation
   - Filters appointments by date

### Form Hooks

6. **useTreatmentPlanForm()**
   - Manages treatment plan form state
   - Handles validation
   - Manages submission

7. **useAppointmentForm()**
   - Manages appointment form state
   - Handles validation
   - Manages submission

### Utility Hooks

8. **useVirtualizedList()**
   - Manages virtualization logic
   - Handles scroll events
   - Calculates visible items

9. **useLocalStorage()**
   - Manages local storage state
   - Handles serialization
   - Syncs across tabs

10. **useDebounce()**
    - Debounces values
    - Useful for search inputs
    - Prevents excessive API calls

---

## COMPONENT EXTRACTION STRATEGY

### Step 1: Extract Hooks
- Create custom hooks for data fetching
- Create custom hooks for form management
- Create custom hooks for utility functions

### Step 2: Extract Sub-Components
- Extract inline components to separate files
- Extract repeated component patterns
- Create reusable component library

### Step 3: Optimize Performance
- Add React.memo() to components
- Implement lazy loading
- Optimize re-renders

### Step 4: Improve Type Safety
- Add proper TypeScript types
- Create type definitions for props
- Add JSDoc comments

---

## REFACTORING PATTERN

### Before (Large Component)
```typescript
export function Dashboard() {
  // Multiple queries
  const { data: metrics } = useQuery(...);
  const { data: appointments } = useQuery(...);
  const { data: billing } = useQuery(...);
  
  // Complex calculations
  const uniquePatients = useMemo(() => {...}, [appointments]);
  const upcomingAppointments = useMemo(() => {...}, [appointments]);
  const recentActivity = useMemo(() => {...}, [appointments]);
  
  // Inline components
  function ActivityItem() {...}
  
  // Rendering logic
  return (
    <div>
      {/* 400+ lines of JSX */}
    </div>
  );
}
```

### After (Refactored)
```typescript
// Custom hooks
function useDashboardMetrics() {
  return useQuery(...);
}

function useTodayAppointments() {
  return useQuery(...);
}

// Sub-components
function ActivityItem() {...}
function StatCard() {...}
function ScheduleCard() {...}

// Main component
export function Dashboard() {
  const metrics = useDashboardMetrics();
  const appointments = useTodayAppointments();
  
  return (
    <div>
      <StatCard {...metrics} />
      <ScheduleCard appointments={appointments} />
      <ActivityCard activities={recentActivity} />
    </div>
  );
}
```

---

## EXPECTED OUTCOMES

### Code Reduction
- **Dashboard**: 400 → 150 lines (62% ↓)
- **Appointments**: 300 → 120 lines (60% ↓)
- **TreatmentPlanDialog**: 200 → 100 lines (50% ↓)
- **PatientMedicalTab**: 200 → 100 lines (50% ↓)
- **VirtualizedPatientList**: 100 → 60 lines (40% ↓)
- **Total**: 1,200 → 530 lines (56% ↓)

### Quality Improvements
- ✅ Better code organization
- ✅ Improved reusability
- ✅ Enhanced testability
- ✅ Better performance
- ✅ Easier maintenance

### Custom Hooks Created
- 10 custom hooks
- 500+ lines of reusable logic
- Improved code sharing

---

## TIMELINE

### Hour 1-2: Dashboard Refactoring
- Extract hooks
- Extract sub-components
- Optimize performance

### Hour 3-4: Appointments Refactoring
- Extract hooks
- Extract sub-components
- Optimize performance

### Hour 5-6: Treatment & Patient Components
- Extract hooks
- Extract sub-components
- Optimize performance

### Hour 7-8: Testing & Optimization
- Test refactored components
- Performance optimization
- Documentation

---

## SUCCESS CRITERIA

✅ All components compile without errors  
✅ No breaking changes to existing functionality  
✅ 50%+ code reduction in target components  
✅ 10+ custom hooks created  
✅ All components properly typed  
✅ Performance improvements verified  
✅ Documentation updated  

---

## NEXT STEPS

1. Start with Dashboard refactoring
2. Extract custom hooks
3. Extract sub-components
4. Test and verify
5. Move to next component
6. Repeat for all target components
7. Final testing and optimization

---

## NOTES

- Focus on extracting logic into hooks first
- Keep components focused on rendering
- Use TypeScript for better type safety
- Add proper error handling
- Document all custom hooks
- Test performance improvements
