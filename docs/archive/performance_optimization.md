# ⚡ CoreDent PMS - Performance Optimization Report

**Date:** March 15, 2026

## 1. Current Issues & bottlenecks

### 1.1 Unnecessary Re-renders
- **Problem**: Large pages like `Reports.tsx` and `PatientProfile.tsx` pass large objects down to many children without memoization.
- **Impact**: Noticeable UI lag when switching tabs or filtering data.
- **Found**: `Reports.tsx` re-renders all 5+ charts on every date change even if only one chart's data is updated.

### 1.2 Missing List Virtualization
- **Problem**: `PatientList.tsx` renders every patient in a simple `div` map.
- **Impact**: As the practice grows to 1000+ patients, the browser will struggle with DOM node management.
- **Found**: No usage of `@tanstack/react-virtual` or similar in data-heavy views.

### 1.3 Bundle Size
- **Problem**: Although lazy loading is implemented, some heavy libraries (like `recharts`) are included in chunks that load even when not needed immediately.
- **Found**: `recharts` is a large dependency (~400KB) currently used in the main charts bundle.

## 2. Suggested Improvements

### 2.1 Component Optimization
- [ ] **Implement React.memo**: Wrap chart components and data cards in `React.memo` with custom comparison functions.
- [ ] **Optimize Context usage**: Split `AuthContext` if shared state becomes too large, though currently it is manageable.

### 2.2 List Virtualization
- [ ] **Add Virtualization**: Integrate `@tanstack/react-virtual` for:
    - `PatientList.tsx`
    - `AppointmentList.tsx` (in Schedule)
    - `NotesTimeline.tsx`

### 2.3 API & Data Fetching
- [ ] **Prefetching**: Use `queryClient.prefetchQuery` for pages like `PatientProfile` when hovering over a patient link.
- [ ] **Pagination**: Ensure all backend endpoints support `limit` and `offset` (partially done).

---

## 3. Implementation Plan (Quick Wins)

1. **Memoize Charts**:
```typescript
const memoizedChart = React.memo(MyChartComponent);
```

2. **Add virtualization to PatientList**:
```typescript
const virtualizer = useVirtualizer({
  count: patients.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 80,
});
```
