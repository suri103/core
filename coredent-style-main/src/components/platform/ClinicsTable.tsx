// ============================================
// Platform console — clinics table with suspend/reactivate
// ============================================

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { PauseCircle, PlayCircle } from 'lucide-react';
import type { PlatformClinic } from '@/services/platformApi';

interface ClinicsTableProps {
  clinics: PlatformClinic[];
  isLoading: boolean;
  onToggle: (clinic: PlatformClinic) => void;
}

export function ClinicsTable({ clinics, isLoading, onToggle }: ClinicsTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12" />)}
      </div>
    );
  }
  if (clinics.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          No clinics found. Try a different search.
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
              <TableHead>Clinic</TableHead>
              <TableHead>Users</TableHead>
              <TableHead>Patients</TableHead>
              <TableHead>Country</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {clinics.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-xs text-muted-foreground">{c.email ?? c.public_slug}</div>
                </TableCell>
                <TableCell>{c.user_count}</TableCell>
                <TableCell>{c.patient_count}</TableCell>
                <TableCell>{c.country ?? '—'}</TableCell>
                <TableCell className="text-xs">
                  {new Date(c.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <Badge variant={c.is_active ? 'default' : 'destructive'}>
                    {c.is_active ? 'Active' : 'Suspended'}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant={c.is_active ? 'destructive' : 'outline'}
                    onClick={() => onToggle(c)}
                  >
                    {c.is_active ? (
                      <><PauseCircle className="h-4 w-4 mr-1" /> Suspend</>
                    ) : (
                      <><PlayCircle className="h-4 w-4 mr-1" /> Reactivate</>
                    )}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
