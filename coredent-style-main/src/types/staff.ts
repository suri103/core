// ============================================
// CoreDent PMS - Staff Types & Role Permissions
// ============================================

import type { UserRole } from './api';

export type StaffStatus = 'active' | 'inactive' | 'pending';

export interface StaffMember {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  status: StaffStatus;
  avatarUrl?: string;
  lastLoginAt?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface StaffInvitation {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  invitedByName: string;
  expiresAt: string;
  createdAt?: string;
}

export interface InviteStaffRequest {
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
}

export interface UpdateStaffRequest {
  firstName?: string;
  lastName?: string;
  email?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface RolePermissionDetails {
  label: string;
  color: string;
  permissions: string[];
}

export const rolePermissions: Record<UserRole, RolePermissionDetails> = {
  owner: {
    label: 'Practice Owner',
    color: 'bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20',
    permissions: ['*'],
  },
  admin: {
    label: 'Administrator',
    color: 'bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20',
    permissions: ['*'],
  },
  dentist: {
    label: 'Dentist',
    color: 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20',
    permissions: ['clinical', 'scheduling', 'patients'],
  },
  hygienist: {
    label: 'Hygienist',
    color: 'bg-sky-500/10 text-sky-500 hover:bg-sky-500/20 border-sky-500/20',
    permissions: ['clinical_limited', 'scheduling', 'patients'],
  },
  front_desk: {
    label: 'Front Desk',
    color: 'bg-purple-500/10 text-purple-500 hover:bg-purple-500/20 border-purple-500/20',
    permissions: ['scheduling', 'patients', 'billing_limited'],
  },
  group_owner: {
    label: 'Group Owner',
    color: 'bg-indigo-500/10 text-indigo-500 hover:bg-indigo-500/20 border-indigo-500/20',
    permissions: ['enterprise_analytics', 'enterprise_locations'],
  },
  group_admin: {
    label: 'Group Administrator',
    color: 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20',
    permissions: ['enterprise_analytics', 'enterprise_locations'],
  },
  accountant: {
    label: 'Accountant',
    color: 'bg-teal-500/10 text-teal-500 hover:bg-teal-500/20 border-teal-500/20',
    permissions: ['billing', 'payments', 'reports_revenue'],
  },
  super_admin: {
    label: 'Platform Admin',
    color: 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20',
    permissions: ['platform_console'],
  },
};
