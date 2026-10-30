/**
 * PatientListEmpty Component
 * Empty state for patient list
 */

import React from 'react';

interface PatientListEmptyProps {
  isLoading?: boolean;
}

/**
 * Empty state component for patient list
 */
export const PatientListEmpty = React.memo(function PatientListEmpty({
  isLoading = false,
}: PatientListEmptyProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading patients...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-center">
        <p className="text-muted-foreground">No patients found</p>
      </div>
    </div>
  );
});
