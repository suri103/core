import React from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { PatientCard } from './PatientCard.memo';
import type { Patient } from '@/types/api';

interface VirtualizedPatientListProps {
  patients: Patient[];
  onSelect?: (patient: Patient) => void;
  onPatientClick?: (patient: Patient) => void;
  isLoading?: boolean;
  containerRef?: React.RefObject<HTMLDivElement>;
}

/**
 * VirtualizedPatientList - High-performance patient list with virtualization
 * 
 * This component uses @tanstack/react-virtual to efficiently render large patient lists
 * by only rendering visible items in the viewport. This significantly improves performance
 * when dealing with thousands of patients.
 * 
 * Features:
 * - Virtual scrolling for large datasets
 * - Smooth scrolling experience
 * - Memory efficient rendering
 * - Customizable item rendering
 */
export function VirtualizedPatientList({
  patients,
  onPatientClick,
  isLoading = false,
  containerRef: externalContainerRef,
}: VirtualizedPatientListProps) {
  const internalContainerRef = React.useRef<HTMLDivElement>(null);
  const containerRef = externalContainerRef || internalContainerRef;

  // Set up virtualization
  const rowVirtualizer = useVirtualizer({
    count: patients.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 120, // Estimated height of each patient card
    overscan: 5, // Render 5 items above and below visible area
  });

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

  if (patients.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-muted-foreground">No patients found</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-[calc(100vh-200px)] overflow-auto"
      style={{ contain: 'strict' }}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const patient = patients[virtualRow.index];
          return (
            <div
              key={patient.id}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <PatientCard 
                patient={patient} 
                onSelect={() => onPatientClick?.(patient)}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
