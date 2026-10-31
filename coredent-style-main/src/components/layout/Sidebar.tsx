// ============================================
// CoreDent PMS - Sidebar Navigation
// Organized clinical, operations, financial & admin sections
// ============================================

import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/auth-context';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
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

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: 'Clinical',
    items: [
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
        label: 'Imaging',
        icon: Image,
        href: '/imaging',
        roles: ['owner', 'admin', 'dentist', 'hygienist'],
      },
    ],
  },
  {
    title: 'Operations',
    items: [
      {
        label: 'Online Booking',
        icon: Calendar,
        href: '/online-booking',
        roles: ['owner', 'admin', 'dentist'],
      },
      {
        label: 'Communications',
        icon: MessageSquare,
        href: '/communications',
        roles: ['owner', 'admin', 'front_desk'],
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
        label: 'Inventory',
        icon: Boxes,
        href: '/inventory',
        roles: ['owner', 'admin', 'dentist', 'hygienist', 'front_desk'],
      },
    ],
  },
  {
    title: 'Financial',
    items: [
      {
        label: 'Billing',
        icon: CreditCard,
        href: '/billing',
        roles: ['owner', 'admin', 'front_desk', 'accountant'],
      },
      {
        label: 'Payments',
        icon: DollarSign,
        href: '/payments',
        roles: ['owner', 'admin', 'front_desk', 'accountant'],
      },
      {
        label: 'Insurance',
        icon: Shield,
        href: '/insurance',
        roles: ['owner', 'admin', 'front_desk'],
      },
      {
        label: 'Reports & Analytics',
        icon: BarChart3,
        href: '/reports',
        roles: ['owner', 'admin', 'accountant'],
      },
    ],
  },
  {
    title: 'Administration',
    items: [
      {
        label: 'Settings',
        icon: Settings,
        href: '/settings',
        roles: ['owner', 'admin'],
      },
      {
        label: 'Staff Management',
        icon: Users,
        href: '/admin/staff-management',
        roles: ['owner', 'admin'],
      },
      {
        label: 'Subscriptions',
        icon: CreditCard,
        href: '/subscriptions',
        roles: ['owner', 'admin'],
      },
      {
        label: 'Security & Compliance',
        icon: ShieldCheck,
        href: '/admin/security',
        roles: ['owner', 'admin'],
      },
      {
        label: 'Data Migration',
        icon: Database,
        href: '/admin/migration',
        roles: ['owner', 'admin'],
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
        roles: ['super_admin'],
      },
    ],
  },
];

export function Sidebar({ collapsed, mobileOpen, onToggle, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const { hasRole } = useAuth();

  // Filter items in each section based on user role
  const filteredSections = navSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) =>
        item.roles.some((role) => hasRole(role))
      ),
    }))
    .filter((section) => section.items.length > 0);

  const sidebarContent = (isMobile: boolean) => (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Logo Header */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b px-4">
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

      {/* Practice Location Switcher */}
      {(!collapsed || isMobile) && (
        <div className="shrink-0">
          <LocationSwitcher />
        </div>
      )}

      {/* Scrollable Navigation - Flex-1 so it stops cleanly above the footer */}
      <ScrollArea className="flex-1 min-h-0">
        <TooltipProvider delayDuration={0}>
          <nav className="flex flex-col p-2 pb-6 space-y-4">
            {filteredSections.map((section, idx) => (
              <div key={section.title} className="space-y-1">
                {/* Section title (expanded desktop & mobile only) */}
                {(!collapsed || isMobile) ? (
                  <div className="px-3 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/60 select-none">
                    {section.title}
                  </div>
                ) : (
                  idx > 0 && <div className="my-2 border-t border-border/50" />
                )}

                {section.items.map((item) => {
                  const isActive =
                    location.pathname === item.href ||
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
                              className={cn(
                                'w-full h-9 mb-1',
                                isActive && 'bg-primary/10 text-primary font-bold'
                              )}
                            >
                              <Icon className="h-4 w-4" />
                            </Button>
                          </NavLink>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                          <span className="font-medium">{item.label}</span>
                        </TooltipContent>
                      </Tooltip>
                    );
                  }

                  return (
                    <NavLink
                      key={item.href}
                      to={item.href}
                      onClick={isMobile ? onMobileClose : undefined}
                    >
                      <Button
                        variant={isActive ? 'secondary' : 'ghost'}
                        className={cn(
                          'w-full justify-start gap-3 h-9 px-3 text-sm font-medium',
                          isActive && 'bg-primary/10 text-primary font-semibold'
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{item.label}</span>
                      </Button>
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </nav>
        </TooltipProvider>
      </ScrollArea>

      {/* Collapse Toggle Footer (desktop only) - Non-overlapping shrink-0 element */}
      {!isMobile && (
        <div className="shrink-0 border-t p-2 bg-card">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className="w-full h-9 text-muted-foreground hover:text-foreground"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                <span>Collapse</span>
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300 hidden lg:flex flex-col',
          collapsed ? 'w-16' : 'w-64'
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
          'fixed left-0 top-0 z-50 h-screen w-72 border-r bg-card transition-transform duration-300 lg:hidden flex flex-col',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent(true)}
      </aside>
    </>
  );
}
