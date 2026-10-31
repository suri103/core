// ============================================
// CoreDent PMS - Main Top Header Navigation
// ============================================

import React from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Menu,
  Settings,
  LogOut,
  ChevronDown,
  Building2,
  Shield,
} from 'lucide-react';

interface HeaderProps {
  onMobileMenuToggle: () => void;
}

function getInitials(firstName?: string, lastName?: string): string {
  if (!firstName && !lastName) return 'U';
  const first = firstName?.trim()?.charAt(0) || '';
  const last = lastName?.trim()?.charAt(0) || '';
  return (first + last).toUpperCase() || 'U';
}

function formatRole(role?: string): string {
  if (!role) return '';
  return role
    .split('_')
    .map((word) => (word?.charAt(0) || '').toUpperCase() + (word?.slice(1) || ''))
    .join(' ');
}

// Map path to friendly section title
function getRouteTitle(pathname: string): string {
  if (pathname.startsWith('/dashboard')) return 'Dashboard';
  if (pathname.startsWith('/patients')) return 'Patients';
  if (pathname.startsWith('/schedule')) return 'Schedule';
  if (pathname.startsWith('/chart')) return 'Dental Chart';
  if (pathname.startsWith('/treatment-plans')) return 'Treatment Plans';
  if (pathname.startsWith('/notes')) return 'Clinical Notes';
  if (pathname.startsWith('/billing')) return 'Billing';
  if (pathname.startsWith('/revenue')) return 'Revenue';
  if (pathname.startsWith('/reports')) return 'Reports';
  if (pathname.startsWith('/online-booking')) return 'Online Booking';
  if (pathname.startsWith('/inventory')) return 'Inventory';
  if (pathname.startsWith('/documents')) return 'Documents';
  if (pathname.startsWith('/marketing')) return 'Marketing';
  if (pathname.startsWith('/enterprise')) return 'Enterprise HQ';
  if (pathname.startsWith('/settings')) return 'Settings';
  if (pathname.startsWith('/admin/migration')) return 'Data Migration';
  if (pathname.startsWith('/admin/security')) return 'Security & Compliance';
  if (pathname.startsWith('/admin/staff')) return 'Staff Management';
  if (pathname.startsWith('/insurance')) return 'Insurance';
  if (pathname.startsWith('/imaging')) return 'Imaging Hub';
  if (pathname.startsWith('/labs')) return 'Lab Management';
  if (pathname.startsWith('/referrals')) return 'Referrals';
  if (pathname.startsWith('/communications')) return 'Communications';
  if (pathname.startsWith('/payments')) return 'Payments';
  if (pathname.startsWith('/subscriptions')) return 'Subscriptions';
  if (pathname.startsWith('/platform')) return 'Platform Console';
  return 'Dashboard';
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const title = getRouteTitle(location.pathname);
  const initials = getInitials(user?.firstName, user?.lastName);
  const formattedRole = formatRole(user?.role);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch {
      navigate('/login');
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b bg-card/80 backdrop-blur px-4 sm:px-6">
      {/* Left side: Mobile menu button + Current section title */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onMobileMenuToggle}
          className="lg:hidden h-9 w-9 text-muted-foreground hover:text-foreground"
          aria-label="Open mobile menu"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
          {user?.practiceName && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground ml-3 pl-3 border-l border-border">
              <Building2 className="h-3.5 w-3.5" />
              <span className="font-medium max-w-[200px] truncate">{user.practiceName}</span>
            </div>
          )}
        </div>
      </div>

      {/* Right side: User menu dropdown */}
      <div className="flex items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="flex items-center gap-3 px-2 py-1.5 h-auto hover:bg-accent/60 rounded-lg group"
            >
              <Avatar className="h-8 w-8 rounded-full border border-primary/20 bg-primary/10 text-primary font-semibold text-xs">
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>

              <div className="hidden md:flex flex-col items-start text-left">
                <span className="text-sm font-semibold leading-tight text-foreground">
                  {user?.firstName ? `${user.firstName} ${user.lastName || ''}`.trim() : 'User'}
                </span>
                <span className="text-[11px] text-muted-foreground leading-tight">
                  {formattedRole || 'Staff'}
                </span>
              </div>

              <ChevronDown className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors hidden sm:block" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-semibold leading-none text-foreground">
                  {user?.firstName} {user?.lastName}
                </p>
                <p className="text-xs text-muted-foreground leading-none truncate">
                  {user?.email}
                </p>
                {formattedRole && (
                  <div className="pt-1">
                    <Badge variant="secondary" className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0">
                      {formattedRole}
                    </Badge>
                  </div>
                )}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />

            <DropdownMenuItem asChild className="cursor-pointer">
              <Link to="/settings" className="flex items-center gap-2">
                <Settings className="h-4 w-4 text-muted-foreground" />
                <span>Practice Settings</span>
              </Link>
            </DropdownMenuItem>

            {user?.role === 'super_admin' && (
              <DropdownMenuItem asChild className="cursor-pointer">
                <Link to="/platform/console" className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  <span>Platform Console</span>
                </Link>
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={handleLogout}
              className="text-destructive focus:text-destructive cursor-pointer flex items-center gap-2"
            >
              <LogOut className="h-4 w-4" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
