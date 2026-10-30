// ============================================
// Platform console — cross-tenant user directory table
// ============================================

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { BadgeProps } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { UserX, UserCheck } from 'lucide-react';
import type { PlatformUser } from '@/services/platformApi';

interface UsersTableProps {
  users: PlatformUser[];
  isLoading: boolean;
  onToggleUser?: (user: PlatformUser) => void;
}

const ROLE_COLORS: Record<string, NonNullable<BadgeProps['variant']>> = {
  owner: 'default',
  admin: 'default',
  dentist: 'secondary',
  accountant: 'secondary',
  hygienist: 'secondary',
  front_desk: 'outline',
  group_owner: 'outline',
  group_admin: 'outline',
  super_admin: 'destructive',
};

export function UsersTable({ users, isLoading, onToggleUser }: UsersTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12" />)}
      </div>
    );
  }
  if (users.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          No users found. Try a different search.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Clinic</TableHead>
              <TableHead>Verified</TableHead>
              <TableHead>Last login</TableHead>
              <TableHead>Status</TableHead>
              {onToggleUser && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="font-medium">{u.full_name}</div>
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </TableCell>
                <TableCell>
                  <Badge variant={ROLE_COLORS[u.role] ?? 'outline'}>{u.role}</Badge>
                </TableCell>
                <TableCell>{u.practice_name ?? '—'}</TableCell>
                <TableCell>
                  <Badge variant={u.is_email_verified ? 'default' : 'outline'}>
                    {u.is_email_verified ? 'Yes' : 'No'}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs">
                  {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                </TableCell>
                <TableCell>
                  <Badge variant={u.is_active ? 'default' : 'destructive'}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </TableCell>
                {onToggleUser && (
                  <TableCell className="text-right">
                    {u.role !== 'super_admin' && (
                      <Button
                        size="sm"
                        variant={u.is_active ? 'destructive' : 'outline'}
                        onClick={() => onToggleUser(u)}
                      >
                        {u.is_active ? (
                          <><UserX className="h-4 w-4 mr-1" /> Deactivate</>
                        ) : (
                          <><UserCheck className="h-4 w-4 mr-1" /> Reactivate</>
                        )}
                      </Button>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
