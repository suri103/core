/**
 * Route Configuration
 * Centralized route definitions for better maintainability
 */

import React from 'react';
import type { UserRole } from '@/types/api';

export interface RouteConfig {
  path: string;
  component: React.LazyExoticComponent<() => JSX.Element>;
  roles?: UserRole[];
  title?: string;
  // For routes with dynamic segments like /patients/:id
  children?: Omit<RouteConfig, 'path'>[];
}

// Lazy load all page components
const Landing = React.lazy(() => import('@/pages/Landing'));
const Login = React.lazy(() => import('@/pages/Login'));
const Register = React.lazy(() => import('@/pages/Register'));
const ForgotPassword = React.lazy(() => import('@/pages/ForgotPassword'));
const ResetPassword = React.lazy(() => import('@/pages/ResetPassword'));
const VerifyEmail = React.lazy(() => import('@/pages/VerifyEmail'));
const AcceptInvitation = React.lazy(() => import('@/pages/AcceptInvitation'));
const Dashboard = React.lazy(() => import('@/pages/Dashboard'));
const Schedule = React.lazy(() => import('@/pages/Schedule'));
const PatientList = React.lazy(() => import('@/pages/patients/PatientList'));
const PatientProfile = React.lazy(() => import('@/pages/patients/PatientProfile'));
const DentalChart = React.lazy(() => import('@/pages/DentalChart'));
const TreatmentPlans = React.lazy(() => import('@/pages/TreatmentPlans'));
const Billing = React.lazy(() => import('@/pages/Billing'));
const Reports = React.lazy(() => import('@/pages/Reports'));
const OnlineBooking = React.lazy(() => import('@/pages/OnlineBooking'));
const Inventory = React.lazy(() => import('@/pages/Inventory'));
const ProductAvailability = React.lazy(() => import('@/pages/ProductAvailability'));
const EnterpriseHQ = React.lazy(() => import('@/pages/EnterpriseHQ'));
const Settings = React.lazy(() => import('@/pages/Settings'));
const ClinicalNotes = React.lazy(() => import('@/pages/ClinicalNotes'));
const Insurance = React.lazy(() => import('@/pages/Insurance'));
const ImagingHub = React.lazy(() => import('@/pages/ImagingHub'));
const Appointments = React.lazy(() => import('@/pages/Appointments'));
const LabManagement = React.lazy(() => import('@/pages/LabManagement'));
const Referrals = React.lazy(() => import('@/pages/Referrals'));
const Communications = React.lazy(() => import('@/pages/Communications'));
const Payments = React.lazy(() => import('@/pages/Payments'));
const PublicBooking = React.lazy(() => import('@/pages/PublicBooking'));
const BookingSuccess = React.lazy(() => import('@/pages/BookingSuccess'));
// M7 FIX: BillingPortal removed â€” it was a decorative page rendering
// hardcoded fake invoices/payment plans and a fabricated "$8,420 collected"
// claim. Real billing lives at /billing.
const ReferralHub = React.lazy(() => import('@/pages/ReferralHub'));
const LabLogistics = React.lazy(() => import('@/pages/LabLogistics'));
const Subscriptions = React.lazy(() => import('@/pages/Subscriptions'));
const NotFound = React.lazy(() => import('@/pages/NotFound'));
const PatientPortal = React.lazy(() => import('@/pages/PatientPortal'));
const DataMigration = React.lazy(() => import('@/pages/admin/DataMigration'));
const SecurityCompliance = React.lazy(() => import('@/pages/admin/SecurityCompliance'));
const StaffManagement = React.lazy(() => import('@/pages/admin/StaffManagement'));
const ForceChangePassword = React.lazy(() => import('@/pages/ForceChangePassword'));
// Platform (super-admin) console — SaaS operator, cross-tenant by design.
const PlatformConsole = React.lazy(() => import('@/pages/platform/PlatformConsole'));
// Legal / policy pages (public)
const Privacy = React.lazy(() => import('@/pages/legal/Privacy'));
const Terms = React.lazy(() => import('@/pages/legal/Terms'));
const DpaPage = React.lazy(() => import('@/pages/legal/Dpa'));
const SecurityLegal = React.lazy(() => import('@/pages/legal/SecurityPage'));
const RefundPolicy = React.lazy(() => import('@/pages/legal/RefundPolicy'));
const ContactPage = React.lazy(() => import('@/pages/legal/Contact'));

/**
 * Public routes (no authentication required)
 */
export const publicRoutes: RouteConfig[] = [
  { path: '/', component: Landing },
  { path: '/login', component: Login },
  { path: '/register', component: Register },
  { path: '/forgot-password', component: ForgotPassword },
  { path: '/reset-password', component: ResetPassword },
  { path: '/verify-email', component: VerifyEmail },
  { path: '/accept-invitation', component: AcceptInvitation },
  // Public booking portal
  { path: '/book/success', component: BookingSuccess },
  { path: '/book/:practiceSlug/:slug', component: PublicBooking },
  // Patient self-service portal
  { path: '/patient-portal', component: PatientPortal },
  // Legal / policy pages (public, linked from footer + auth screens)
  { path: '/legal/privacy', component: Privacy },
  { path: '/legal/terms', component: Terms },
  { path: '/legal/dpa', component: DpaPage },
  { path: '/legal/security', component: SecurityLegal },
  { path: '/legal/refunds', component: RefundPolicy },
  { path: '/legal/contact', component: ContactPage },
];

/**
 * Protected routes grouped by feature area
 * Each group can have its own role-based access control
 */
export const protectedRoutes: RouteConfig[] = [
  // Dashboard
  {
    path: '/dashboard',
    component: Dashboard,
    title: 'Dashboard',
  },

  // Patient Management
  {
    path: '/patients',
    component: PatientList,
    roles: ['owner', 'admin', 'dentist', 'front_desk'],
    title: 'Patients',
  },
  {
    path: '/patients/:id',
    component: PatientProfile,
    roles: ['owner', 'admin', 'dentist', 'front_desk'],
    title: 'Patient Profile',
  },

  // Scheduling
  {
    path: '/schedule/*',
    component: Schedule,
    roles: ['owner', 'admin', 'dentist', 'front_desk'],
    title: 'Schedule',
  },

  // Clinical - Dentist only
  {
    path: '/chart',
    component: DentalChart,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Dental Chart',
  },
  {
    path: '/chart/*',
    component: DentalChart,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Dental Chart',
  },

  // Treatment Plans
  {
    path: '/treatment-plans',
    component: TreatmentPlans,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Treatment Plans',
  },
  {
    path: '/treatment-plans/*',
    component: TreatmentPlans,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Treatment Plans',
  },

  // Clinical Notes
  {
    path: '/notes',
    component: ClinicalNotes,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Clinical Notes',
  },
  {
    path: '/notes/:id',
    component: ClinicalNotes,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Clinical Notes',
  },
  {
    path: '/notes/*',
    component: ClinicalNotes,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Clinical Notes',
  },

  // Billing
  {
    path: '/billing',
    component: Billing,
    roles: ['owner', 'admin', 'front_desk', 'accountant'],
    title: 'Billing',
  },
  {
    path: '/billing/*',
    component: Billing,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Billing',
  },

  // Revenue uses the live reports and billing-backed analytics page.
  {
    path: '/revenue',
    component: Reports,
    roles: ['owner', 'admin', 'accountant'],
    title: 'Revenue',
  },

  // Reports - Owner and Admin only
  {
    path: '/reports',
    component: Reports,
    roles: ['owner', 'admin', 'accountant'],
    title: 'Reports',
  },
  {
    path: '/reports/*',
    component: Reports,
    roles: ['owner', 'admin'],
    title: 'Reports',
  },

  // Staff online booking. Dentists may manage requests; page configuration is
  // intentionally limited to owner/admin by the page and backend contracts.
  {
    path: '/online-booking',
    component: OnlineBooking,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Online Booking',
  },

  // Inventory reads are available to authenticated practice staff. The page
  // and backend enforce owner/admin for write operations.
  {
    path: '/inventory',
    component: Inventory,
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
    title: 'Inventory',
  },

  // Honest capability gates for modules without live staff workflows.
  {
    path: '/documents',
    component: ProductAvailability,
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
    title: 'Documents',
  },
  {
    path: '/marketing',
    component: ProductAvailability,
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
    title: 'Marketing',
  },

  // Enterprise HQ is available only to server-authorized group roles.
  {
    path: '/enterprise/hq',
    component: EnterpriseHQ,
    roles: ['group_owner', 'group_admin'],
    title: 'Enterprise HQ',
  },

  // Settings
  {
    path: '/settings',
    component: Settings,
    roles: ['owner', 'admin'],
    title: 'Settings',
  },
  {
    path: '/settings/*',
    component: Settings,
    roles: ['owner', 'admin'],
    title: 'Settings',
  },

  // Admin Data Migration
  {
    path: '/admin/migration',
    component: DataMigration,
    roles: ['owner', 'admin'],
    title: 'Data Migration',
  },

  // Security & Compliance
  {
    path: '/admin/security',
    component: SecurityCompliance,
    roles: ['owner', 'admin'],
    title: 'Security & Compliance',
  },

  // Referral Hub
  {
    path: '/referrals/hub',
    component: ReferralHub,
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
    title: 'Referral Hub',
  },

  // Lab Logistics
  {
    path: '/lab/logistics',
    component: LabLogistics,
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
    title: 'Lab Logistics',
  },

  // Insurance Management
  {
    path: '/insurance',
    component: Insurance,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Insurance',
  },
  {
    path: '/insurance/*',
    component: Insurance,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Insurance',
  },

  // Imaging Management
  {
    path: '/imaging',
    component: ImagingHub,
    roles: ['owner', 'admin', 'dentist', 'hygienist'],
    title: 'Imaging',
  },

  // Appointments
  {
    path: '/appointments',
    component: Appointments,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Appointments',
  },

  // Lab Management
  {
    path: '/labs',
    component: LabManagement,
    roles: ['owner', 'admin', 'dentist'],
    title: 'Lab Management',
  },

  // Referrals
  {
    path: '/referrals',
    component: Referrals,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Referrals',
  },

  // Communications
  {
    path: '/communications',
    component: Communications,
    roles: ['owner', 'admin', 'front_desk'],
    title: 'Communications',
  },

  // Payments
  {
    path: '/payments',
    component: Payments,
    roles: ['owner', 'admin', 'front_desk', 'accountant'],
    title: 'Payments',
  },

  // Subscriptions
  {
    path: '/subscriptions',
    component: Subscriptions,
    roles: ['owner', 'admin'],
    title: 'Subscriptions',
  },

  // Staff Management
  {
    path: '/admin/staff-management',
    component: StaffManagement,
    roles: ['owner', 'admin'],
    title: 'Staff Management',
  },

  // Force password change (first login after admin provisioning)
  // No role restriction â€” the ProtectedRoute gate allows this through when
  // mustChangePassword is armed, regardless of role.
  {
    path: '/force-change-password',
    component: ForceChangePassword,
    title: 'Change Password',
  },

  // Platform (super-admin) console — SaaS operator only. Server enforces the
  // same role gate on every /api/v1/platform/* call.
  {
    path: '/platform/console',
    component: PlatformConsole,
    roles: ['super_admin'],
    title: 'Platform Console',
  },
];

export const notFoundRoute: RouteConfig = {
  path: '*',
  component: NotFound,
  title: 'Not Found',
};
