import { AllergiesCard } from './AllergiesCard';
import { DentalHistoryCard } from './DentalHistoryCard';
import { MedicalConditionsCard } from './MedicalConditionsCard';
import { MedicationsCard } from './MedicationsCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { HeartHandshake } from 'lucide-react';
import type { MedicalHistory, DentalHistory } from '@/types/patient';

interface PatientMedicalTabProps {
  medicalHistory: MedicalHistory;
  dentalHistory: DentalHistory;
}

export function PatientMedicalTab({
  medicalHistory,
  dentalHistory,
}: PatientMedicalTabProps) {
  return (
    <div className="space-y-6">
      {/* Cards Row */}
      <div className="grid gap-6 md:grid-cols-2">
        <MedicalConditionsCard conditions={medicalHistory.conditions} />
        <AllergiesCard allergies={medicalHistory.allergies} />
        <MedicationsCard medications={medicalHistory.medications} />
        <DentalHistoryCard dentalHistory={dentalHistory} />
      </div>

      {/* Details breakdown */}
      <Card className="border border-border bg-card/60 backdrop-blur-md">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <HeartHandshake className="h-5 w-5 text-primary" />
            Physician & Systemic Details
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 text-sm">
          <div className="space-y-1">
            <span className="block text-xs text-muted-foreground uppercase tracking-wider">Primary Care Physician</span>
            <span className="font-semibold text-foreground">{medicalHistory.primaryPhysician || 'Not Specified'}</span>
          </div>

          <div className="space-y-1">
            <span className="block text-xs text-muted-foreground uppercase tracking-wider">Physician Phone</span>
            <span className="font-semibold text-foreground">{medicalHistory.physicianPhone || 'Not Specified'}</span>
          </div>

          <div className="space-y-1">
            <span className="block text-xs text-muted-foreground uppercase tracking-wider">Blood Type</span>
            <span className="font-semibold text-foreground">{medicalHistory.bloodType || 'Unknown'}</span>
          </div>

          {medicalHistory.surgeries && medicalHistory.surgeries.length > 0 && (
            <div className="col-span-1 sm:col-span-2 lg:col-span-3 space-y-1.5 pt-2">
              <span className="block text-xs text-muted-foreground uppercase tracking-wider">Surgical History</span>
              <p className="text-foreground leading-relaxed font-medium">{medicalHistory.surgeries.join(', ')}</p>
            </div>
          )}

          {medicalHistory.familyHistory && medicalHistory.familyHistory.length > 0 && (
            <div className="col-span-1 sm:col-span-2 lg:col-span-3 space-y-1.5 pt-2 border-t border-border/50">
              <span className="block text-xs text-muted-foreground uppercase tracking-wider">Family Medical History</span>
              <p className="text-foreground leading-relaxed font-medium">{medicalHistory.familyHistory.join(', ')}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
