import { describe, it, expect, beforeEach } from 'vitest';
import { dentalChartApi } from '../dentalChartApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { DentalChart, ToothProcedure } from '@/types/dentalChart';

const mockChart: DentalChart = {
  id: 'chart-1',
  patientId: 'p-1',
  patientName: 'John Doe',
  teeth: [
    {
      number: 14,
      name: 'Upper Right First Molar',
      condition: 'sound',
      procedures: [],
    },
  ],
  updatedAt: '2026-06-01T00:00:00Z',
  lastUpdated: '2026-06-01T00:00:00Z',
};

const mockProcedure: ToothProcedure = {
  id: 'proc-1',
  code: 'D1110',
  description: 'Adult prophylaxis',
  cost: 120,
  status: 'planned',
  date: '2026-06-01',
};

describe('dentalChartApi', () => {
  beforeEach(() => server.resetHandlers());

  it('getChart returns the chart for a patient', async () => {
    server.use(
      http.get('/api/v1/patients/p-1/chart', () => HttpResponse.json(mockChart)),
    );
    const result = await dentalChartApi.getChart('p-1');
    expect(result).toEqual(mockChart);
  });

  it('updateToothCondition PUTs the new condition and returns the chart', async () => {
    server.use(
      http.put(
        '/api/v1/patients/p-1/chart/teeth/14/condition',
        async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            ...mockChart,
            teeth: [
              { number: 14, name: 'Upper Right First Molar', condition: body.condition, procedures: [] },
            ],
          });
        },
      ),
    );
    const result = await dentalChartApi.updateToothCondition('p-1', 14, 'decay');
    expect(result.teeth[0].condition).toBe('decay');
  });

  it('addProcedure posts a new procedure and returns it', async () => {
    server.use(
      http.post(
        '/api/v1/patients/p-1/chart/teeth/14/procedures',
        async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            { ...mockProcedure, ...body, id: 'proc-2' },
            { status: 201 },
          );
        },
      ),
    );
    const result = await dentalChartApi.addProcedure('p-1', 14, {
      code: 'D1110',
      description: 'Cleaning',
      cost: 120,
      status: 'planned',
      date: '2026-06-01',
    });
    expect(result.id).toBe('proc-2');
  });

  it('updateProcedureStatus sends a PUT', async () => {
    server.use(
      http.put(
        '/api/v1/patients/p-1/chart/teeth/14/procedures/proc-1/status',
        () => HttpResponse.json({ message: 'updated' }),
      ),
    );
    await expect(
      dentalChartApi.updateProcedureStatus('p-1', 14, 'proc-1', 'completed'),
    ).resolves.toBeUndefined();
  });

  it('deleteProcedure sends a DELETE', async () => {
    server.use(
      http.delete(
        '/api/v1/patients/p-1/chart/teeth/14/procedures/proc-1',
        () => HttpResponse.json({ message: 'deleted' }),
      ),
    );
    await expect(
      dentalChartApi.deleteProcedure('p-1', 14, 'proc-1'),
    ).resolves.toBeUndefined();
  });
});
