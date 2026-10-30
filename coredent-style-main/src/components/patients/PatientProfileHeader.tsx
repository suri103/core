import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Edit3,
  ShieldAlert,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import type { PatientRecord } from '@/types/patient';

interface PatientProfileHeaderProps {
  patient: PatientRecord;
  onEdit: () => void;
  onStatusChange: () => void;
  region: string;
}

export function PatientProfileHeader({
  patient,
  onEdit,
  onStatusChange,
  region: _region,
}: PatientProfileHeaderProps) {
  const calculateAge = (dobString: string) => {
    if (!dobString) return 'N/A';
    const dob = new Date(dobString);
    const diff = Date.now() - dob.getTime();
    const ageDate = new Date(diff);
    return Math.abs(ageDate.getUTCFullYear() - 1970);
  };

  const isActive = patient.status === 'active';

  return (
    <Card className="overflow-hidden border border-border bg-card/60 backdrop-blur-md">
      <CardContent className="p-6">
        <div className="flex flex-col md:flex-row gap-6 items-start justify-between">
          <div className="flex flex-col sm:flex-row gap-5 items-start sm:items-center">
            {/* Avatar / Icon */}
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 text-primary">
              <User className="h-8 w-8" />
            </div>

            {/* Info details */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="text-2xl font-bold tracking-tight text-foreground">
                  {patient.firstName} {patient.lastName}
                </h2>
                <Badge variant="outline" className={`${
                  isActive 
                    ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20' 
                    : 'bg-neutral-500/10 text-neutral-500 hover:bg-neutral-500/20 border-neutral-500/20'
                  } capitalize border px-2 py-0 cursor-pointer`}
                  onClick={onStatusChange}
                >
                  {isActive ? (
                    <CheckCircle className="h-3 w-3 mr-1" />
                  ) : (
                    <XCircle className="h-3 w-3 mr-1" />
                  )}
                  {patient.status}
                </Badge>
                {patient.medicalHistory?.allergies?.length > 0 && (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <ShieldAlert className="h-3 w-3" /> Medical Alert
                  </Badge>
                )}
              </div>

              {/* Bio details line */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" /> 
                  DOB: {patient.dateOfBirth} ({calculateAge(patient.dateOfBirth)} years old)
                </span>
                <span className="h-1 w-1 rounded-full bg-border hidden sm:inline" />
                <span className="capitalize">{patient.gender}</span>
                {patient.insuranceInfo?.provider && (
                  <>
                    <span className="h-1 w-1 rounded-full bg-border hidden sm:inline" />
                    <span>Insurance: {patient.insuranceInfo.provider}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex gap-2 w-full md:w-auto">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={onEdit} 
              className="flex-1 sm:flex-none border-border bg-background hover:bg-accent text-foreground gap-1.5"
            >
              <Edit3 className="h-4 w-4" /> Edit Profile
            </Button>
            <Button 
              variant={isActive ? "destructive" : "default"}
              size="sm" 
              onClick={onStatusChange}
              className="flex-1 sm:flex-none gap-1.5"
            >
              {isActive ? 'Deactivate' : 'Activate'}
            </Button>
          </div>
        </div>

        {/* Contact Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 border-t border-border/50 mt-6 pt-5 text-sm">
          <div className="flex items-center gap-2 text-foreground">
            <Phone className="h-4 w-4 text-muted-foreground" />
            <span>{patient.phone || 'No phone'}</span>
          </div>
          <div className="flex items-center gap-2 text-foreground">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="truncate">{patient.email || 'No email'}</span>
          </div>
          {patient.address && (
            <div className="flex items-center gap-2 text-foreground sm:col-span-2 md:col-span-1">
              <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="truncate">
                {patient.address.street}, {patient.address.city}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
