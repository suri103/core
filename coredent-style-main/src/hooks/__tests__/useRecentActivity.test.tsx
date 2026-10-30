import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useRecentActivity } from '../useRecentActivity';
import type { Appointment } from '@/types/api';

describe('useRecentActivity Hook', () => {
  const mockAppointments: Appointment[] = [
    {
      id: '1',
      patientId: 'p-1',
      patientName: 'John Doe',
      startTime: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
      endTime: new Date(Date.now() - 1800000).toISOString(),
      status: 'confirmed',
      type: 'exam',
      providerId: 'd-1',
      providerName: 'Dr. Smith',
      operatoryId: 'c-1',
      operatoryName: 'Chair 1',
      notes: '',
      createdAt: '',
      updatedAt: '',
    },
    {
      id: '2',
      patientId: 'p-2',
      patientName: 'Jane Smith',
      startTime: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
      endTime: new Date(Date.now() - 5400000).toISOString(),
      status: 'completed',
      type: 'root_canal',
      providerId: 'd-1',
      providerName: 'Dr. Smith',
      operatoryId: 'c-1',
      operatoryName: 'Chair 1',
      notes: '',
      createdAt: '',
      updatedAt: '',
    },
  ];

  it('should process and sort appointments correctly', () => {
    const { result } = renderHook(() => useRecentActivity(mockAppointments));

    expect(result.current.activities).toHaveLength(2);
    // Should be sorted by startTime descending (most recent first)
    expect(result.current.activities[0].description).toContain('John Doe');
    expect(result.current.activities[0].description).toBe('John Doe - Exam');

    expect(result.current.activities[1].description).toContain('Jane Smith');
    expect(result.current.activities[1].title).toBe('Appointment completed');
    expect(result.current.activities[1].description).toBe('Jane Smith - Root Canal');
  });

  it('should respect the limit option', () => {
    const { result } = renderHook(() => useRecentActivity(mockAppointments, { limit: 1 }));
    expect(result.current.activities).toHaveLength(1);
    expect(result.current.activities[0].description).toContain('John Doe');
  });

  it('should handle empty or missing values gracefully', () => {
    const emptyAppt: Appointment = {
      id: '3',
      patientId: 'p-3',
      patientName: 'Anonymous',
      startTime: new Date().toISOString(),
      endTime: new Date().toISOString(),
      status: 'scheduled',
      type: 'other', // empty type
      providerId: 'd-1',
      providerName: 'Dr. Smith',
      operatoryId: 'c-1',
      operatoryName: 'Chair 1',
      notes: '',
      createdAt: '',
      updatedAt: '',
    };

    const { result } = renderHook(() => useRecentActivity([emptyAppt]));
    expect(result.current.activities[0].description).toBe('Anonymous - Other');
  });
});
