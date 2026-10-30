/**
 * DentalHistoryCard Component
 * Displays patient dental history
 */

import React from 'react';
import { format, parseISO } from 'date-fns';
import { Stethoscope } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { PatientRecord } from '@/types/patient';

interface DentalHistoryCardProps {
  dentalHistory: PatientRecord['dentalHistory'];
}

/**
 * Card displaying dental history
 */
export const DentalHistoryCard = React.memo(function DentalHistoryCard({
  dentalHistory,
}: DentalHistoryCardProps) {
  const history = dentalHistory || ({} as PatientRecord['dentalHistory']);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-primary" />
          Dental History
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-muted-foreground">Last Cleaning:</span>
            <span className="ml-2">
              {history.lastCleaning
                ? format(parseISO(history.lastCleaning), 'MMM d, yyyy')
                : 'Unknown'}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Last X-Rays:</span>
            <span className="ml-2">
              {history.lastXrays
                ? format(parseISO(history.lastXrays), 'MMM d, yyyy')
                : 'Unknown'}
            </span>
          </div>
        </div>
        <Separator />
        <div className="flex flex-wrap gap-2">
          {history.gumDiseaseHistory && (
            <Badge variant="outline">Gum Disease History</Badge>
          )}
          {history.toothSensitivity && (
            <Badge variant="outline">Tooth Sensitivity</Badge>
          )}
          {history.grindsClenches && (
            <Badge variant="outline">Grinds/Clenches</Badge>
          )}
          {history.hasImplants && (
            <Badge variant="outline">Has Implants</Badge>
          )}
          {history.missingTeeth && history.missingTeeth.length > 0 && (
            <Badge variant="outline">
              Missing Teeth: {history.missingTeeth.join(', ')}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
});
