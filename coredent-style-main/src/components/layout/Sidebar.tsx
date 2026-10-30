// ============================================
// CoreDent PMS - Sidebar Navigation
// Role-based menu visibility with mobile support
// ============================================

import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/auth-context';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { LocationSwitcher } from './LocationSwitcher';
import {
  LayoutDashboard,
  Users,
  Calendar,
  ClipboardList,
  FileText,
  CreditCard,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  Stethoscope,
  X,
  Shield,
  Image,
  Beaker,
  UserPlus,
  MessageSquare,
  DollarSign,
  Database,
  ShieldCheck,
  Boxes,
  Building2,
  Megaphone,
  Server,
} from 'lucide-react';
import type { UserRole } from '@/types/api';

interface SidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

interface NavItem {
  label: string;
  icon: React.ElementType;
  href: string;
  roles: UserRole[];
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    icon: LayoutDashboard,
    href: '/dashboard',
    roles: ['owner', 'admin', 'dentist', 'front_desk', 'accountant'],
  },
  {
    label: 'Patients',
    icon: Users,
    href: '/patients',
    roles: ['owner', 'admin', 'dentist', 'front_desk'],
  },
  {
    label: 'Schedule',
    icon: Calendar,
    href: '/schedule',
    roles: ['owner', 'admin', 'dentist', 'front_desk'],
  },
  {
    label: 'Dental Chart',
    icon: Stethoscope,
    href: '/chart',
    roles: ['owner', 'admin', 'dentist'],
  },
  {
    label: 'Treatment Plans',
    icon: ClipboardList,
    href: '/treatment-plans',
    roles: ['owner', 'admin', 'dentist'],
  },
  {
    label: 'Clinical Notes',
    icon: FileText,
    href: '/notes',
    roles: ['owner', 'admin', 'dentist'],
  },
  {
    label: 'Billing',
    icon: CreditCard,
    href: '/billing',
    // accountant (2026-09): finance staff own billing; no clinical access.
    roles: ['owner', 'admin', 'front_desk', 'accountant'],
  },
  {
    label: 'Reports',
    icon: BarChart3,
    href: '/reports',
    roles: ['owner', 'admin', 'accountant'],
  },
  {
    label: 'Revenue',
    icon: BarChart3,
    href: '/revenue',
    roles: ['owner', 'admin', 'accountant'],
  },
  {
    label: 'Online Booking',
    icon: Calendar,
    href: '/online-booking',
    roles: ['owner', 'admin', 'dentist'],
  },
  {
    label: 'Inventory',
    icon: Boxes,
    href: '/inventory',
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
  },
  {
    label: 'Documents',
    icon: FileText,
    href: '/documents',
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
  },
  {
    label: 'Marketing',
    icon: Megaphone,
    href: '/marketing',
    roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
  },
  {
    label: 'Enterprise HQ',
    icon: Building2,
    href: '/enterprise/hq',
    roles: ['group_owner', 'group_admin'],
  },
  {
    label: 'Platform Console',
    icon: Server,
    href: '/platform/console',
    // super_admin (2026-09): SaaS operator console — cross-tenant by design.
    roles: ['super_admin'],
  },
  {
    label: 'Settings',
    icon: Settings,
    href: '/settings',
    roles: ['owner', 'admin'],
  },
  {
    label: 'Data Migration',
    icon: Database,
    href: '/admin/migration',
    roles: ['owner', 'admin'],
  },
  {
    label: 'Security & Compliance',
    icon: ShieldCheck,
    href: '/admin/security',
    roles: ['owner', 'admin'],
  },
  {
    label: 'Insurance',
    icon: Shield,
    href: '/insurance',
    roles: ['owner', 'admin', 'front_desk'],
  },
  {
    label: 'Imaging',
    icon: Image,
    href: '/imaging',
    roles: ['owner', 'admin', 'dentist', 'hygienist'],
  },
  {
    label: 'Lab Work',
    icon: Beaker,
    href: '/labs',
    roles: ['owner', 'admin', 'dentist'],
  },
  {
    label: 'Referrals',
    icon: UserPlus,
    href: '/referrals',
    roles: ['owner', 'admin', 'front_desk'],
  },
  {
    label: 'Communications',
    icon: MessageSquare,
    href: '/communications',
    roles: ['owner', 'admin', 'front_desk'],
  },
  {
    label: 'Payments',
    icon: DollarSign,
    href: '/payments',
    roles: ['owner', 'admin', 'front_desk'],
  },
  {
    label: 'Subscriptions',
    icon: CreditCard,
    href: '/subscriptions',
    roles: ['owner', 'admin'],
  },
];

export function Sidebar({ collapsed, mobileOpen, onToggle, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const { hasRole } = useAuth();

  const filteredItems = navItems.filter(item => 
    item.roles.some(role => hasRole(role))
  );

  const sidebarContent = (isMobile: boolean) => (
    <>
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b px-4">
        {(!collapsed || isMobile) && (
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Stethoscope className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-semibold text-lg">CoreDent</span>
          </div>
        )}
        {collapsed && !isMobile && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary mx-auto">
            <Stethoscope className="h-5 w-5 text-primary-foreground" />
          </div>
        )}
        {/* Mobile close button */}
        {isMobile && (
          <Button variant="ghost" size="icon" onClick={onMobileClose} className="lg:hidden">
            <X className="h-5 w-5" />
          </Button>
        )}
      </div>

      {(!collapsed || isMobile) && <LocationSwitcher />}

      {/* Navigation */}
      <ScrollArea className="h-[calc(100vh-8rem)]">
        <nav className="flex flex-col gap-1 p-2">
          {filteredItems.map((item) => {
            const isActive = location.pathname === item.href || 
                            location.pathname.startsWith(item.href + '/');
            const Icon = item.icon;

            if (collapsed && !isMobile) {
              return (
                <Tooltip key={item.href} delayDuration={0}>
                  <TooltipTrigger asChild>
                    <NavLink to={item.href}>
                      <Button
                        variant={isActive ? 'secondary' : 'ghost'}
                        size="icon"
                        className="w-full"
                      >
                        <Icon className="h-5 w-5" />
                      </Button>
                    </NavLink>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return (
              <NavLink key={item.href} to={item.href} onClick={isMobile ? onMobileClose : undefined}>
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  className={cn(
                    "w-full justify-start gap-3",
                    isActive && "bg-secondary"
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {item.label}
                </Button>
              </NavLink>
            );
          })}
        </nav>
      </ScrollArea>

      {/* Collapse Toggle (desktop only) */}
      {!isMobile && (
        <div className="absolute bottom-0 left-0 right-0 border-t p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className="w-full"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                Collapse
              </>
            )}
          </Button>
        </div>
      )}
    </>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300 hidden lg:block",
          collapsed ? "w-16" : "w-64"
        )}
      >
        {sidebarContent(false)}
      </aside>

      {/* Mobile Overlay Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-50 h-screen w-72 border-r bg-card transition-transform duration-300 lg:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {sidebarContent(true)}
      </aside>
    </>
  );
}
