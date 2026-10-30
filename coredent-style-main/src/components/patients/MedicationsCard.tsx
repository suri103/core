/**
 * MedicationsCard Component
 * Displays patient medications
 */

import React from 'react';
import { Pill } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface MedicationsCardProps {
  medications: string[];
}

/**
 * Card displaying current medications
 */
export const MedicationsCard = React.memo(function MedicationsCard({
  medications,
}: MedicationsCardProps) {
  const safeMedications = Array.isArray(medications) ? medications : (medications ? [String(medications)] : []);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Pill className="h-5 w-5 text-blue-500" />
          Current Medications
        </CardTitle>
      </CardHeader>
      <CardContent>
        {safeMedications.length > 0 ? (
          <ul className="space-y-2">
            {safeMedications.map((med, i) => (
              <li key={i} className="text-sm">
                {med}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-muted-foreground">No medications</span>
        )}
      </CardContent>
    </Card>
  );
});
