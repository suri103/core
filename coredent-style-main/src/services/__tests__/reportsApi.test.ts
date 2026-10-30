import { describe, it, expect, vi, beforeEach } from 'vitest';
import { reportsApi } from '../reportsApi';
import { apiClient } from '../api';
import type { DashboardMetrics, DateRange } from '@/types/reports';

vi.mock('../api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockMetrics: DashboardMetrics = {
  appointments: {
    total: 100,
    completed: 80,
    cancelled: 15,
    noShow: 5,
    completionRate: 80,
    noShowRate: 5,
    byType: [{ type: 'checkup', count: 100 }],
    byDay: [],
  },
  revenue: {
    totalRevenue: 10000,
    totalCollected: 8000,
    totalOutstanding: 2000,
    averagePerVisit: 100,
    byMonth: [{ month: 'Jan', revenue: 10000, collected: 8000 }],
    byProcedure: [],
  },
  treatmentAcceptance: {
    proposedPlans: 10,
    acceptedPlans: 8,
    completedPlans: 4,
    acceptanceRate: 80,
    completionRate: 40,
  },
  chairUtilization: {
    totalChairs: 4,
    averageUtilization: 75,
    byChair: [{ chair: 'Chair 1', utilization: 75, appointments: 25 }],
    peakHours: [],
    byDayOfWeek: [],
  },
};

const dateRange: DateRange = {
  from: new Date('2026-01-01T00:00:00Z'),
  to: new Date('2026-01-31T00:00:00Z'),
};

describe('reportsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('gets dashboard metrics', async () => {
    const mockResponse = { success: true, data: mockMetrics };
    vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

    const result = await reportsApi.getDashboardMetrics(dateRange);
    expect(apiClient.get).toHaveBeenCalledWith('/reports/dashboard', {
      from: '2026-01-01',
      to: '2026-01-31',
    });
    expect(result).toEqual(mockResponse);
  });

  describe('exportToCSV', () => {
    it('exports appointments report to CSV', () => {
      const csv = reportsApi.exportToCSV('appointments', mockMetrics, dateRange);
      expect(csv).toContain('Appointments Report');
      expect(csv).toContain('checkup,100');
    });

    it('exports revenue report to CSV', () => {
      const csv = reportsApi.exportToCSV('revenue', mockMetrics, dateRange);
      expect(csv).toContain('Revenue Report');
      expect(csv).toContain('Jan,$10000,$8000');
    });

    it('exports treatment acceptance report to CSV', () => {
      const csv = reportsApi.exportToCSV('treatment', mockMetrics, dateRange);
      expect(csv).toContain('Treatment Acceptance Report');
      expect(csv).toContain('Proposed Plans,10');
      expect(csv).toContain('Acceptance Rate,80%');
    });

    it('exports utilization report to CSV', () => {
      const csv = reportsApi.exportToCSV('utilization', mockMetrics, dateRange);
      expect(csv).toContain('Chair Utilization Report');
      expect(csv).toContain('Chair 1,75%,25');
    });
  });

  describe('downloadCSV', () => {
    it('creates a download link and triggers click', () => {
      // Mock URL.createObjectURL and revokeObjectURL
      const createObjectURLMock = vi.fn().mockReturnValue('blob:url');
      const revokeObjectURLMock = vi.fn();
      global.URL.createObjectURL = createObjectURLMock;
      global.URL.revokeObjectURL = revokeObjectURLMock;

      // Mock click on anchor element
      const clickMock = vi.fn();
      const mockAnchor = {
        href: '',
        download: '',
        click: clickMock,
      };
      const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);
      const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockAnchor as any);
      const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockAnchor as any);

      reportsApi.downloadCSV('test-report', 'col1,col2\nval1,val2');

      expect(createObjectURLMock).toHaveBeenCalled();
      expect(createElementSpy).toHaveBeenCalledWith('a');
      expect(mockAnchor.download).toBe('test-report.csv');
      expect(mockAnchor.href).toBe('blob:url');
      expect(appendChildSpy).toHaveBeenCalledWith(mockAnchor);
      expect(clickMock).toHaveBeenCalled();
      expect(removeChildSpy).toHaveBeenCalledWith(mockAnchor);
      expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:url');

      // Clean up spies
      createElementSpy.mockRestore();
      appendChildSpy.mockRestore();
      removeChildSpy.mockRestore();
    });
  });
});
