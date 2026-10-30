// ============================================
// CoreDent PMS - Staff Management Page
// Admin panel for managing staff and invitations
// ============================================

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Search,
  UserPlus,
  MoreHorizontal,
  Mail,
  Shield,
  UserX,
  UserCheck,
  Clock,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { rolePermissions } from '@/types/staff';
import type { StaffMember, StaffInvitation } from '@/types/staff';
import { InviteStaffDialog } from '@/components/admin/InviteStaffDialog';
import { EditStaffDialog } from '@/components/admin/EditStaffDialog';
import { formatDistanceToNow } from 'date-fns';
import { staffApi } from '@/services/staffApi';
import { useToast } from '@/hooks/use-toast';
const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  inactive: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
};

export default function StaffManagement() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [editingStaff, setEditingStaff] = useState<StaffMember | null>(null);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [invitations, setInvitations] = useState<StaffInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;
    const loadStaff = async () => {
      setIsLoading(true);
      try {
        // Call APIs sequentially to keep the response types narrow (Promise.all
        // widens the tuple union and breaks the `setStaff` inference below).
        const staffResponse = await staffApi.list();
        if (!isActive) return;
        if (staffResponse.success && staffResponse.data) {
          setStaff(staffResponse.data.data);
        } else {
          setStaff([]);
          toast({
            title: 'Error',
            description: staffResponse.error?.message || 'Failed to load staff',
            variant: 'destructive',
          });
        }

        const invitationsResponse = await staffApi.listInvitations();
        if (!isActive) return;
        if (invitationsResponse.success && invitationsResponse.data) {
          setInvitations(invitationsResponse.data);
        } else {
          setInvitations([]);
          toast({
            title: 'Error',
            description: invitationsResponse.error?.message || 'Failed to load invitations',
            variant: 'destructive',
          });
        }
      } catch (error) {
        if (!isActive) return;
        setStaff([]);
        setInvitations([]);
        toast({
          title: 'Error',
          description: error instanceof Error ? error.message : 'Failed to load staff data',
          variant: 'destructive',
        });
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };
    loadStaff();
    return () => {
      isActive = false;
    };
  }, [toast]);

  // Filter staff based on search and filters
  const filteredStaff = staff.filter((staff) => {
    const matchesSearch =
      searchQuery === '' ||
      `${staff.firstName} ${staff.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
      staff.email.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesRole = roleFilter === 'all' || staff.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || staff.status === statusFilter;

    return matchesSearch && matchesRole && matchesStatus;
  });

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  const handleDeactivate = async (member: StaffMember) => {
    try {
      const response = await staffApi.deactivate(member.id);
      if (!response.success || !response.data) {
        throw new Error(response.error?.message || 'Failed to deactivate staff');
      }
      setStaff((prev) => prev.map((s) => (s.id === member.id ? response.data! : s)));
      toast({
        title: 'Staff deactivated',
        description: `${member.firstName} ${member.lastName} has been deactivated`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to deactivate staff',
        variant: 'destructive',
      });
    }
  };

  const handleReactivate = async (member: StaffMember) => {
    try {
      const response = await staffApi.reactivate(member.id);
      if (!response.success || !response.data) {
        throw new Error(response.error?.message || 'Failed to reactivate staff');
      }
      setStaff((prev) => prev.map((s) => (s.id === member.id ? response.data! : s)));
      toast({
        title: 'Staff reactivated',
        description: `${member.firstName} ${member.lastName} has been reactivated`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to reactivate staff',
        variant: 'destructive',
      });
    }
  };

  const handleResendInvitation = async (invitation: StaffInvitation) => {
    try {
      const response = await staffApi.resendInvitation(invitation.id);
      if (!response.success || !response.data) {
        throw new Error(response.error?.message || 'Failed to resend invitation');
      }
      setInvitations((prev) => prev.map((i) => (i.id === invitation.id ? response.data! : i)));
      toast({
        title: 'Invitation resent',
        description: `A new invitation has been sent to ${invitation.email}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to resend invitation',
        variant: 'destructive',
      });
    }
  };

  const handleCancelInvitation = async (invitation: StaffInvitation) => {
    try {
      await staffApi.cancelInvitation(invitation.id);
      setInvitations((prev) => prev.filter((i) => i.id !== invitation.id));
      toast({
        title: 'Invitation cancelled',
        description: `Invitation to ${invitation.email} has been cancelled`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to cancel invitation',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Staff Management</h1>
          <p className="text-muted-foreground">
            Manage team members, roles, and invitations
          </p>
        </div>
        <Button onClick={() => setIsInviteOpen(true)} className="gap-2">
          <UserPlus className="h-4 w-4" />
          Invite Staff
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Staff</p>
                <p className="text-2xl font-bold">{staff.length}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Shield className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Active</p>
                <p className="text-2xl font-bold">
                  {staff.filter((s) => s.status === 'active').length}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <UserCheck className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Invites</p>
                <p className="text-2xl font-bold">{invitations.length}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900">
                <Clock className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Dentists</p>
                <p className="text-2xl font-bold">
                  {staff.filter((s) => s.role === 'dentist').length}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
                <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for Staff and Invitations */}
      <Tabs defaultValue="staff" className="space-y-4">
        <TabsList>
          <TabsTrigger value="staff">Staff Members</TabsTrigger>
          <TabsTrigger value="invitations">
            Pending Invitations
            {invitations.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {invitations.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Staff Members Tab */}
        <TabsContent value="staff">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row gap-4">
                {/* Search */}
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search by name or email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
                {/* Filters */}
                <div className="flex gap-2">
                  <Select value={roleFilter} onValueChange={setRoleFilter}>
                    <SelectTrigger className="w-[140px]">
                      <SelectValue placeholder="Role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Roles</SelectItem>
                      <SelectItem value="owner">Owner</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="dentist">Dentist</SelectItem>
                      <SelectItem value="front_desk">Front Desk</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
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
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Active</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        Loading staff...
                      </TableCell>
                    </TableRow>
                  ) : filteredStaff.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        No staff members found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredStaff.map((staff) => (
                      <TableRow key={staff.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar>
                            <AvatarImage src={staff.avatarUrl} />
                            <AvatarFallback className="bg-primary text-primary-foreground">
                              {getInitials(staff.firstName, staff.lastName)}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-medium">
                              {staff.firstName} {staff.lastName}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {staff.email}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={rolePermissions[staff.role].color}>
                          {rolePermissions[staff.role].label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[staff.status]}>
                          {staff.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {staff.lastLoginAt
                          ? formatDistanceToNow(new Date(staff.lastLoginAt), {
                              addSuffix: true,
                            })
                          : 'Never'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setEditingStaff(staff)}>
                              <Shield className="mr-2 h-4 w-4" />
                              Edit Role
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Mail className="mr-2 h-4 w-4" />
                              Send Message
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {staff.status === 'active' ? (
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => handleDeactivate(staff)}
                              >
                                <UserX className="mr-2 h-4 w-4" />
                                Deactivate
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => handleReactivate(staff)}>
                                <UserCheck className="mr-2 h-4 w-4" />
                                Reactivate
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pending Invitations Tab */}
        <TabsContent value="invitations">
          <Card>
            <CardHeader>
              <CardTitle>Pending Invitations</CardTitle>
              <CardDescription>
                Staff members who haven't accepted their invitation yet
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                  Loading invitations...
                </div>
              ) : invitations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Mail className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium">No pending invitations</h3>
                  <p className="text-muted-foreground">
                    All invited staff have accepted their invitations
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Invited By</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invitations.map((invitation) => (
                      <TableRow key={invitation.id}>
                        <TableCell className="font-medium">
                          {invitation.email}
                        </TableCell>
                        <TableCell>
                          <Badge className={rolePermissions[invitation.role].color}>
                            {rolePermissions[invitation.role].label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {invitation.invitedByName}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDistanceToNow(new Date(invitation.expiresAt), {
                            addSuffix: true,
                          })}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Resend"
                              onClick={() => handleResendInvitation(invitation)}
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive"
                              title="Cancel"
                              onClick={() => handleCancelInvitation(invitation)}
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <InviteStaffDialog
        open={isInviteOpen}
        onOpenChange={setIsInviteOpen}
        onSuccess={(invitation) => setInvitations((prev) => [invitation, ...prev])}
      />
      <EditStaffDialog
        staff={editingStaff}
        open={!!editingStaff}
        onOpenChange={(open) => !open && setEditingStaff(null)}
        onSuccess={(updated) =>
          setStaff((prev) => prev.map((member) => (member.id === updated.id ? updated : member)))
        }
      />
    </div>
  );
}
