import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useScheduling } from '../useScheduling';

const { mockGetChairs, mockGetProviders, mockGetAppointmentTypes, mockGetAppointments } = vi.hoisted(() => ({
  mockGetChairs: vi.fn(),
  mockGetProviders: vi.fn(),
  mockGetAppointmentTypes: vi.fn(),
  mockGetAppointments: vi.fn(),
}));

vi.mock('@/services/schedulingApi', () => ({
  schedulingApi: {
    getChairs: mockGetChairs,
    getProviders: mockGetProviders,
    getAppointmentTypes: mockGetAppointmentTypes,
    getAppointments: mockGetAppointments,
  },
}));

describe('useScheduling Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetChairs.mockResolvedValue([{ id: 'chair-1', name: 'Chair 1' }]);
    mockGetProviders.mockResolvedValue([{ id: 'prov-1', name: 'Dr. Smith' }]);
    mockGetAppointmentTypes.mockResolvedValue([{ id: 'type-1', name: 'Checkup', duration: 30 }]);
    mockGetAppointments.mockResolvedValue([
      { id: '1', patientId: 'p-1', patientName: 'John Doe', startTime: new Date('2026-06-28T10:00:00Z'), endTime: new Date('2026-06-28T10:30:00Z'), duration: 30, type: 'Checkup', chairId: 'chair-1', providerId: 'prov-1', providerName: 'Dr. Smith', status: 'scheduled' }
    ]);
  });

  it('should initialize with default states', () => {
    const { result } = renderHook(() => useScheduling());
    expect(result.current.view).toBe('day');
    expect(result.current.appointments).toEqual([]);
    expect(result.current.chairs).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should load data successfully for day view', async () => {
    const { result } = renderHook(() => useScheduling());
    
    await act(async () => {
      await result.current.loadData();
    });

    expect(mockGetChairs).toHaveBeenCalled();
    expect(mockGetProviders).toHaveBeenCalled();
    expect(mockGetAppointmentTypes).toHaveBeenCalled();
    expect(mockGetAppointments).toHaveBeenCalled();

    expect(result.current.chairs).toHaveLength(1);
    expect(result.current.appointments).toHaveLength(1);
    expect(result.current.appointments[0].patientName).toBe('John Doe');
    expect(result.current.isLoading).toBe(false);
  });

  it('should load data successfully for week view', async () => {
    const { result } = renderHook(() => useScheduling());
    
    act(() => {
      result.current.setView('week');
    });

    await act(async () => {
      await result.current.loadData();
    });

    expect(mockGetAppointments).toHaveBeenCalled();
  });

  it('should load data successfully for month view', async () => {
    const { result } = renderHook(() => useScheduling());
    
    act(() => {
      result.current.setView('month');
    });

    await act(async () => {
      await result.current.loadData();
    });

    expect(mockGetAppointments).toHaveBeenCalled();
  });

  it('should handle error during loadData', async () => {
    const testError = new Error('Network Error');
    mockGetChairs.mockRejectedValueOnce(testError);

    const { result } = renderHook(() => useScheduling());

    await act(async () => {
      await result.current.loadData();
    });

    expect(result.current.error).toBe(testError);
    expect(result.current.isLoading).toBe(false);
  });

  it('should handle navigation', () => {
    const { result } = renderHook(() => useScheduling());
    const initialDate = new Date(result.current.currentDate);

    // Go to Next day
    act(() => {
      result.current.goToNext();
    });
    const expectedNextDate = new Date(initialDate);
    expectedNextDate.setDate(initialDate.getDate() + 1);
    expect(result.current.currentDate.toDateString()).toBe(expectedNextDate.toDateString());

    // Go to Previous day
    act(() => {
      result.current.goToPrevious();
    });
    expect(result.current.currentDate.toDateString()).toBe(initialDate.toDateString());

    // Go to Date
    const targetDate = new Date('2026-12-25');
    act(() => {
      result.current.goToDate(targetDate);
    });
    expect(result.current.currentDate.toDateString()).toBe(targetDate.toDateString());

    // Go to Today
    act(() => {
      result.current.goToToday();
    });
    expect(result.current.currentDate.toDateString()).toBe(new Date().toDateString());
  });

  it('should handle navigation in week and month views', () => {
    const { result } = renderHook(() => useScheduling());
    
    // Week View
    act(() => {
      result.current.setView('week');
    });
    const initialWeekDate = new Date(result.current.currentDate);
    act(() => {
      result.current.goToNext();
    });
    expect(result.current.currentDate.getTime() - initialWeekDate.getTime()).toBe(7 * 24 * 60 * 60 * 1000);
    act(() => {
      result.current.goToPrevious();
    });
    expect(result.current.currentDate.getTime()).toBe(initialWeekDate.getTime());

    // Month View
    act(() => {
      result.current.setView('month');
    });
    const initialMonthDate = new Date(result.current.currentDate);
    act(() => {
      result.current.goToNext();
    });
    expect(result.current.currentDate.getMonth()).toBe((initialMonthDate.getMonth() + 1) % 12);
    act(() => {
      result.current.goToPrevious();
    });
    expect(result.current.currentDate.getMonth()).toBe(initialMonthDate.getMonth());
  });

  it('should handle appointment modifications (add, update, remove)', () => {
    const { result } = renderHook(() => useScheduling());

    const newAppt = {
      id: '2',
      patientId: 'p-2',
      patientName: 'Jane Smith',
      startTime: new Date('2026-06-28T11:00:00Z'),
      endTime: new Date('2026-06-28T11:30:00Z'),
      duration: 30,
      type: 'Cleaning',
      chairId: 'chair-1',
      providerId: 'prov-1',
      providerName: 'Dr. Smith',
      status: 'scheduled' as const
    };

    // Add
    act(() => {
      result.current.addAppointment(newAppt);
    });
    expect(result.current.appointments).toHaveLength(1);
    expect(result.current.appointments[0].patientName).toBe('Jane Smith');

    // Update
    act(() => {
      result.current.updateAppointment('2', { patientName: 'Jane Doe' });
    });
    expect(result.current.appointments[0].patientName).toBe('Jane Doe');

    // Select and Update
    act(() => {
      result.current.setSelectedAppointment(result.current.appointments[0]);
    });
    expect(result.current.selectedAppointment?.patientName).toBe('Jane Doe');
    
    act(() => {
      result.current.updateAppointment('2', { patientName: 'Jane Smith Updated' });
    });
    expect(result.current.selectedAppointment?.patientName).toBe('Jane Smith Updated');

    // Remove
    act(() => {
      result.current.removeAppointment('2');
    });
    expect(result.current.appointments).toHaveLength(0);
    expect(result.current.selectedAppointment).toBeNull();
  });
});

