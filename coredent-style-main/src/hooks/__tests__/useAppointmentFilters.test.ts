/**
 * useAppointmentFilters Hook Tests
 */

import { renderHook } from '@testing-library/react';
import { useAppointmentFilters, useUniqueDentists, getStatusColor } from '../useAppointmentFilters';
import type { Appointment } from '@/services/appointmentsApi';

describe('useAppointmentFilters', () => {
  const mockAppointments: Appointment[] = [
    { id: '1', patientId: 'p1', patient: 'John Doe', patientName: 'John Doe', providerId: 'd1', providerName: 'Dr. Smith', startTime: '2026-08-12T13:00:00.000Z', endTime: '2026-08-12T13:30:00.000Z', status: 'confirmed', time: '9:00', type: 'Checkup', dentist: 'Dr. Smith', duration: '30' },
    { id: '2', patientId: 'p2', patient: 'Jane Smith', patientName: 'Jane Smith', providerId: 'd2', providerName: 'Dr. Jones', startTime: '2026-08-12T14:00:00.000Z', endTime: '2026-08-12T14:45:00.000Z', status: 'scheduled', time: '10:00', type: 'Cleaning', dentist: 'Dr. Jones', duration: '45' },
    { id: '3', patientId: 'p3', patient: 'Bob Johnson', patientName: 'Bob Johnson', providerId: 'd1', providerName: 'Dr. Smith', startTime: '2026-08-12T15:00:00.000Z', endTime: '2026-08-12T15:30:00.000Z', status: 'confirmed', time: '11:00', type: 'Checkup', dentist: 'Dr. Smith', duration: '30' },
  ];

  it('should return all appointments when no filters applied', () => {
    const { result } = renderHook(() => useAppointmentFilters(mockAppointments, {}));

    expect(result.current).toHaveLength(3);
  });

  it('should filter appointments by search term', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters(mockAppointments, { searchTerm: 'Jane' })
    );

    expect(result.current).toHaveLength(1);
    expect(result.current[0].patient).toBe('Jane Smith');
  });

  it('should filter appointments by status', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters(mockAppointments, { status: 'confirmed' })
    );

    expect(result.current).toHaveLength(2);
    expect(result.current.every((apt) => apt.status === 'confirmed')).toBe(true);
  });

  it('should filter appointments by dentist', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters(mockAppointments, { dentist: 'Dr. Smith' })
    );

    expect(result.current).toHaveLength(2);
    expect(result.current.every((apt) => apt.dentist === 'Dr. Smith')).toBe(true);
  });

  it('should apply multiple filters', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters(mockAppointments, {
        searchTerm: 'Checkup',
        dentist: 'Dr. Smith',
      })
    );

    expect(result.current).toHaveLength(2);
    expect(result.current.every((apt) => apt.type === 'Checkup' && apt.dentist === 'Dr. Smith')).toBe(true);
  });

  it('should handle empty appointments array', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters([], { searchTerm: 'John' })
    );

    expect(result.current).toHaveLength(0);
  });

  it('should be case-insensitive for search', () => {
    const { result } = renderHook(() =>
      useAppointmentFilters(mockAppointments, { searchTerm: 'jane' })
    );

    expect(result.current).toHaveLength(1);
  });
});

describe('useUniqueDentists', () => {
  it('should return unique dentists sorted alphabetically', () => {
    const appointments: Appointment[] = [
      { id: '1', patientId: 'p1', patient: 'John', patientName: 'John', providerId: 'd1', providerName: 'Dr. Smith', startTime: '2026-08-12T13:00:00.000Z', endTime: '2026-08-12T13:30:00.000Z', status: 'confirmed', time: '9:00', type: 'Checkup', dentist: 'Dr. Smith', duration: '30' },
      { id: '2', patientId: 'p2', patient: 'Jane', patientName: 'Jane', providerId: 'd2', providerName: 'Dr. Jones', startTime: '2026-08-12T14:00:00.000Z', endTime: '2026-08-12T14:45:00.000Z', status: 'scheduled', time: '10:00', type: 'Cleaning', dentist: 'Dr. Jones', duration: '45' },
      { id: '3', patientId: 'p3', patient: 'Bob', patientName: 'Bob', providerId: 'd1', providerName: 'Dr. Smith', startTime: '2026-08-12T15:00:00.000Z', endTime: '2026-08-12T15:30:00.000Z', status: 'confirmed', time: '11:00', type: 'Checkup', dentist: 'Dr. Smith', duration: '30' },
    ];

    const { result } = renderHook(() => useUniqueDentists(appointments));

    expect(result.current).toEqual(['Dr. Jones', 'Dr. Smith']);
  });

  it('should handle empty appointments', () => {
    const { result } = renderHook(() => useUniqueDentists([]));

    expect(result.current).toEqual([]);
  });
});

describe('getStatusColor', () => {
  it('should return correct color for confirmed status', () => {
    expect(getStatusColor('Confirmed')).toBe('bg-green-500');
  });

  it('should return correct color for pending status', () => {
    expect(getStatusColor('Pending')).toBe('bg-yellow-500');
  });

  it('should return correct color for cancelled status', () => {
    expect(getStatusColor('Cancelled')).toBe('bg-red-500');
  });

  it('should return correct color for completed status', () => {
    expect(getStatusColor('Completed')).toBe('bg-blue-500');
  });

  it('should return default color for unknown status', () => {
    expect(getStatusColor('Unknown')).toBe('bg-gray-500');
  });

  it('should be case-insensitive', () => {
    expect(getStatusColor('confirmed')).toBe('bg-green-500');
    expect(getStatusColor('PENDING')).toBe('bg-yellow-500');
  });
});
