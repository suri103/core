/**
 * MedicalConditionsCard Component
 * Displays patient medical conditions
 */

import React from 'react';
import { Heart } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface MedicalConditionsCardProps {
  conditions: string[];
}

/**
 * Card displaying medical conditions
 */
export const MedicalConditionsCard = React.memo(function MedicalConditionsCard({
  conditions,
}: MedicalConditionsCardProps) {
  const safeConditions = Array.isArray(conditions) ? conditions : (conditions ? [String(conditions)] : []);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Heart className="h-5 w-5 text-red-500" />
          Medical Conditions
        </CardTitle>
      </CardHeader>
      <CardContent>
        {safeConditions.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {safeConditions.map((condition, i) => (
              <Badge key={i} variant="secondary">
                {condition}
              </Badge>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground">None reported</span>
        )}
      </CardContent>
    </Card>
  );
});
