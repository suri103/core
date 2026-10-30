# 🔍 CoreDent PMS - Comprehensive Codebase Audit

**Date:** March 15, 2026  
**Auditor:** Senior Software Architect (Antigravity)  
**Project:** CoreDent Dental Practice Management System  
**Tech Stack:** React + TypeScript (Frontend) | FastAPI + Python (Backend)

---

## 1. Major Architectural Issues

### 1.1 ✅ Strengths
- **Clean Backend Structure**: FastAPI with well-defined `api`, `core`, `models`, and `schemas` layers. Use of modern async `SQLAlchemy 2.0` patterns.
- **Service Layer Frontend**: Clear separation of API logic into dedicated service files (e.g., `reportsApi.ts`, `patientApi.ts`).
- **Type Safety**: Strong TypeScript usage throughout the frontend, reducing runtime errors.
- **Lazy Loading**: Route-based code splitting is correctly implemented in `App.tsx`.
- **Security Headers**: Backend enforces HSTS, X-Content-Type-Options, and other critical headers.

### 1.2 ⚠️ Architectural Concerns
- **Component Bloat**: Several core components exceed 600 lines (e.g., `Reports.tsx`, `PatientProfile.tsx`). These components mix UI layout, state management, and minor business logic, violating the Single Responsibility Principle.
- **Hoisted State Complexity**: Large components like `PatientProfile.tsx` manage multiple dialog states and data fetching internally rather than delegating to custom hooks or sub-components.
- **Inconsistent Error Handling**: While standard toast notifications are used, there is no centralized Error Boundary strategy beyond the root level, nor a unified API mutation hook to handle repetitive try-catch blocks.
- **Implicit Dependency Tracking**: Some services have complex dependencies that are manually managed rather than using a centralized registry or more robust DI patterns in the frontend.

---

## 2. Security Risks

### 2.1 🔴 High Priority
- **Dependency Vulnerabilities**: Several core packages are outdated (FastAPI 0.109, SQLAlchemy 2.0.25). Newer versions contain critical security and performance patches.
- **Audit Read Logging**: The current system tracks data modifications (CREATE/UPDATE/DELETE) but lacks granular logging for data READ access, which is a requirement for full HIPAA compliance.

### 2.2 🟡 Medium Priority
- **SQL Injection Surface**: While SQLAlchemy is used correctly for most queries, some legacy or helper scripts (like `supabase_migration.py`) use string interpolation for SQL extensions.
- **Token Rotation**: While tokens are now in `httpOnly` cookies, the refresh token rotation mechanism needs verification to ensure old tokens are invalidated upon use.
- **Rate Limiting Consistency**: Rate limiting is applied at a global level but should be more aggressively tuned for sensitive endpoints like `/auth/login` and `/auth/password-reset`.

---

## 3. Performance Problems

### 3.1 ⚠️ Issues Identified
- **Missing List Virtualization**: Pages like `PatientList` and `Appointments` render all records in the DOM, which will lead to significant lag as the practice database grows.
- **Unnecessary Re-renders**: Large components like `Reports.tsx` re-render their entire chart collection when the date range changes, rather than using `React.memo` or splitting charts into optimized sub-components.
- **Slow Initial Payload**: Although lazy loading is used for pages, the shared vendors chunk and large component files still result in a heavy initial JS payload.

---

## 4. Refactoring Recommendations

### 4.1 🛠️ Component Splitting (Highest Priority)
- **`Reports.tsx`**: Split into `ReportsContainer`, `ReportsFilters`, and individual `ChartCard` components.
- **`PatientProfile.tsx`**: Extract `PatientSummaryHeader`, `MedicalAlertsBanner`, and individual tab contents into separate files.

### 4.2 🛠️ Shared Hooks & Utilities
- **`useApiData`**: Create a standard hook for data fetching that handles loading, error, and stale states consistently.
- **`useDialog`**: Standardize dialog state management to reduce boilerplate in large pages.

### 4.3 🛠️ Infrastructure Updates
- **Upgrade Backend core**: Move to FastAPI 0.115+ and SQLAlchemy 2.0.35+ for Pydantic v2 performance gains and security fixes.
- **Implement @tanstack/react-virtual**: Add virtualization to all major data tables.

---

## 5. Conclusion
CoreDent is in a **strong pre-production state**. Most "low hanging fruit" security issues have been addressed. The primary focus now should shift to **maintainability** (splitting large components) and **scalability** (virtualization and dependency updates). Addressing these will ensure the codebase remains manageable as the feature set expands.
