import { memo } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Phone, Mail, Calendar } from 'lucide-react';
import type { Patient } from '@/types/api';
import { format } from 'date-fns';

interface PatientCardProps {
  patient: Patient;
  onSelect: (id: string) => void;
}

// Memoized patient card to prevent unnecessary re-renders
export const PatientCard = memo(function PatientCard({ patient, onSelect }: PatientCardProps) {
  const getInitials = (firstName: string | undefined, lastName: string | undefined) => {
    if (!firstName || !lastName) return '?';
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  const handleClick = () => {
    onSelect(patient.id);
  };

  return (
    <Card
      className="cursor-pointer transition-all hover:shadow-md"
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
    >
      <CardHeader className="flex flex-row items-center gap-4 pb-2">
        <Avatar className="h-12 w-12">
          <AvatarFallback className="bg-primary text-primary-foreground">
            {getInitials(patient.firstName, patient.lastName)}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <h3 className="font-semibold text-lg">
            {patient.firstName} {patient.lastName}
          </h3>
          <Badge variant={patient.status === 'active' ? 'default' : 'secondary'}>
            {patient.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4" />
          <span>{patient.phone}</span>
        </div>
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4" />
          <span>{patient.email}</span>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4" />
          <span>DOB: {format(new Date(patient.dateOfBirth), 'MMM d, yyyy')}</span>
        </div>
      </CardContent>
    </Card>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function for better performance
  return (
    prevProps.patient.id === nextProps.patient.id &&
    prevProps.patient.status === nextProps.patient.status &&
    prevProps.patient.updatedAt === nextProps.patient.updatedAt
  );
});
