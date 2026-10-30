/**
 * AllergiesCard Component
 * Displays patient allergies
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface AllergiesCardProps {
  allergies: string[];
}

/**
 * Card displaying allergies
 */
export const AllergiesCard = React.memo(function AllergiesCard({
  allergies,
}: AllergiesCardProps) {
  const safeAllergies = Array.isArray(allergies) ? allergies : (allergies ? [String(allergies)] : []);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Allergies
        </CardTitle>
      </CardHeader>
      <CardContent>
        {safeAllergies.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {safeAllergies.map((allergy, i) => (
              <Badge key={i} variant="destructive">
                {allergy}
              </Badge>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground">No known allergies</span>
        )}
      </CardContent>
    </Card>
  );
});
