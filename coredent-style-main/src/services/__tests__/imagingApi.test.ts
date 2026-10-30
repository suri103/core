import { describe, it, expect, beforeEach } from 'vitest';
import { imagingApi } from '../imagingApi';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import type { PatientImage } from '@/types/imaging';

const mockImage: PatientImage = {
  id: 'img-1',
  patientId: 'p-1',
  imageType: 'xray',
  category: 'bitewing',
  title: 'Bitewing X-ray',
  description: 'Routine checkup',
  toothNumber: '14',
  captureDate: '2026-06-01',
  createdBy: 'staff-1',
  fileUrl: 'https://example.com/xray.png',
  thumbnailUrl: 'https://example.com/xray-thumb.png',
  fileSize: 12345,
  mimeType: 'image/png',
  tags: ['checkup'],
  annotations: [],
  isArchived: false,
  createdAt: '2026-06-01T00:00:00Z',
  updatedAt: '2026-06-01T00:00:00Z',
};

describe('imagingApi', () => {
  beforeEach(() => server.resetHandlers());

  describe('images', () => {
    it('getImages returns the image list', async () => {
      server.use(
        http.get('/api/v1/imaging/images', () => HttpResponse.json([mockImage])),
      );
      const result = await imagingApi.getImages();
      expect(result).toEqual([mockImage]);
    });

    it('getImage returns a single image', async () => {
      server.use(
        http.get('/api/v1/imaging/images/img-1', () => HttpResponse.json(mockImage)),
      );
      const result = await imagingApi.getImage('img-1');
      expect(result).toEqual(mockImage);
    });

    it('uploadImage posts multipart file to the patient images route', async () => {
      let capturedUrl: URL | undefined;
      server.use(
        http.post('/api/v1/imaging/patients/p-1/images', ({ request }) => {
          capturedUrl = new URL(request.url);
          return HttpResponse.json({ ...mockImage, id: 'img-2' }, { status: 201 });
        }),
      );
      const file = new File(['x'], 'xray.png', { type: 'image/png' });
      const result = await imagingApi.uploadImage({
        patientId: 'p-1',
        imageType: 'xray',
        category: 'bitewing',
        title: 'New',
        file,
      });
      expect(result.id).toBe('img-2');
      expect(capturedUrl?.searchParams.get('image_type')).toBe('xray');
      expect(capturedUrl?.searchParams.get('category')).toBe('bitewing');
      expect(capturedUrl?.searchParams.get('title')).toBe('New');
    });

    it('uploadImage sends all supported optional parameters as query params', async () => {
      let capturedUrl: URL | undefined;
      server.use(
        http.post('/api/v1/imaging/patients/p-1/images', ({ request }) => {
          capturedUrl = new URL(request.url);
          return HttpResponse.json({ ...mockImage, id: 'img-3' }, { status: 201 });
        }),
      );
      const file = new File(['x'], 'xray.png', { type: 'image/png' });
      const result = await imagingApi.uploadImage({
        patientId: 'p-1',
        imageType: 'xray',
        category: 'bitewing',
        title: 'New',
        description: 'Detail desc',
        notes: 'Chairside notes',
        toothNumber: '12',
        deviceName: 'Gendex GX-1000',
        deviceSerial: 'SN-42',
        file,
      });
      expect(result.id).toBe('img-3');
      expect(capturedUrl?.searchParams.get('description')).toBe('Detail desc');
      expect(capturedUrl?.searchParams.get('notes')).toBe('Chairside notes');
      expect(capturedUrl?.searchParams.get('tooth_number')).toBe('12');
      expect(capturedUrl?.searchParams.get('device_name')).toBe('Gendex GX-1000');
      expect(capturedUrl?.searchParams.get('device_serial')).toBe('SN-42');
    });

    it('uploadImage throws error on failure', async () => {
      server.use(
        http.post('/api/v1/imaging/patients/p-1/images', () =>
          HttpResponse.json({ message: 'Upload limit exceeded' }, { status: 400 }),
        ),
      );
      const file = new File(['x'], 'xray.png', { type: 'image/png' });
      await expect(
        imagingApi.uploadImage({
          patientId: 'p-1',
          imageType: 'xray',
          category: 'bitewing',
          title: 'New',
          file,
        })
      ).rejects.toThrow('Upload limit exceeded');
    });

    it('updateImage sends a PUT', async () => {
      server.use(
        http.put('/api/v1/imaging/images/img-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockImage, ...body });
        }),
      );
      const result = await imagingApi.updateImage('img-1', { title: 'Updated' });
      expect(result.title).toBe('Updated');
    });

    it('updateImage throws error on failure', async () => {
      server.use(
        http.put('/api/v1/imaging/images/img-1', () =>
          HttpResponse.json({ message: 'Update failed' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.updateImage('img-1', { title: 'Updated' })
      ).rejects.toThrow('Update failed');
    });

    it('deleteImage resolves', async () => {
      server.use(
        http.delete('/api/v1/imaging/images/img-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      await expect(imagingApi.deleteImage('img-1')).resolves.toBeUndefined();
    });

    it('addAnnotation posts the annotation', async () => {
      server.use(
        http.post('/api/v1/imaging/images/img-1/annotations', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            ...mockImage,
            annotations: [{ id: 'ann-1', ...body }],
          });
        }),
      );
      const result = await imagingApi.addAnnotation('img-1', {
        type: 'circle',
        x: 10,
        y: 20,
        width: 30,
        height: 30,
        text: 'Cavity',
        color: '#ff0000',
      });
      expect(result.annotations).toHaveLength(1);
    });

    it('addAnnotation throws error on failure', async () => {
      server.use(
        http.post('/api/v1/imaging/images/img-1/annotations', () =>
          HttpResponse.json({ message: 'Cannot add annotation' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.addAnnotation('img-1', {
          type: 'circle',
          x: 10,
          y: 20,
          width: 30,
          height: 30,
          text: 'Cavity',
          color: '#ff0000',
        })
      ).rejects.toThrow('Cannot add annotation');
    });

    it('deleteAnnotation removes an annotation', async () => {
      server.use(
        http.delete('/api/v1/imaging/images/img-1/annotations/ann-1', () =>
          HttpResponse.json({ ...mockImage, annotations: [] }),
        ),
      );
      const result = await imagingApi.deleteAnnotation('img-1', 'ann-1');
      expect(result.annotations).toEqual([]);
    });

    it('deleteAnnotation throws error on failure', async () => {
      server.use(
        http.delete('/api/v1/imaging/images/img-1/annotations/ann-1', () =>
          HttpResponse.json({ message: 'Cannot delete annotation' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.deleteAnnotation('img-1', 'ann-1')
      ).rejects.toThrow('Cannot delete annotation');
    });
  });

  describe('series', () => {
    it('getSeries returns series', async () => {
      const series = { id: 'ser-1', patientId: 'p-1', name: 'Full mouth', seriesDate: '2026-06-01' };
      server.use(
        http.get('/api/v1/imaging/series', () => HttpResponse.json([series])),
      );
      const result = await imagingApi.getSeries();
      expect(result).toEqual([series]);
    });

    it('getSeriesById returns a single series', async () => {
      const series = { id: 'ser-1', patientId: 'p-1', name: 'Full mouth', seriesDate: '2026-06-01' };
      server.use(
        http.get('/api/v1/imaging/series/ser-1', () => HttpResponse.json(series)),
      );
      const result = await imagingApi.getSeriesById('ser-1');
      expect(result).toEqual(series);
    });

    it('createSeries posts a new series', async () => {
      server.use(
        http.post('/api/v1/imaging/series', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ id: 'ser-2', ...body }, { status: 201 });
        }),
      );
      const result = await imagingApi.createSeries({
        patientId: 'p-1',
        name: 'Panoramic',
        seriesDate: '2026-06-22',
      });
      expect(result.id).toBe('ser-2');
    });

    it('createSeries throws error on failure', async () => {
      server.use(
        http.post('/api/v1/imaging/series', () =>
          HttpResponse.json({ message: 'Creation failed' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.createSeries({
          patientId: 'p-1',
          name: 'Panoramic',
          seriesDate: '2026-06-22',
        })
      ).rejects.toThrow('Creation failed');
    });

    it('updateSeries sends a PUT', async () => {
      const series = { id: 'ser-1', patientId: 'p-1', name: 'Full mouth', seriesDate: '2026-06-01' };
      server.use(
        http.put('/api/v1/imaging/series/ser-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...series, ...body });
        }),
      );
      const result = await imagingApi.updateSeries('ser-1', { name: 'Renamed' });
      expect(result.name).toBe('Renamed');
    });

    it('updateSeries throws error on failure', async () => {
      server.use(
        http.put('/api/v1/imaging/series/ser-1', () =>
          HttpResponse.json({ message: 'Update failed' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.updateSeries('ser-1', { name: 'Renamed' })
      ).rejects.toThrow('Update failed');
    });

    it('deleteSeries resolves', async () => {
      server.use(
        http.delete('/api/v1/imaging/series/ser-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      await expect(imagingApi.deleteSeries('ser-1')).resolves.toBeUndefined();
    });
  });

  describe('templates', () => {
    it('getTemplates returns templates', async () => {
      const tpl = { id: 'tpl-1', name: 'Default', isActive: true, createdAt: '', updatedAt: '' };
      server.use(
        http.get('/api/v1/imaging/templates', () => HttpResponse.json([tpl])),
      );
      const result = await imagingApi.getTemplates();
      expect(result).toEqual([tpl]);
    });

    it('createTemplate posts a new template', async () => {
      server.use(
        http.post('/api/v1/imaging/templates', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ id: 'tpl-2', ...body, createdAt: '', updatedAt: '' }, { status: 201 });
        }),
      );
      const result = await imagingApi.createTemplate({
        name: 'New',
        imageType: 'xray',
        category: 'bitewing',
        isActive: true,
      });
      expect(result.id).toBe('tpl-2');
    });

    it('createTemplate throws error on failure', async () => {
      server.use(
        http.post('/api/v1/imaging/templates', () =>
          HttpResponse.json({ message: 'Creation failed' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.createTemplate({
          name: 'New',
          imageType: 'xray',
          category: 'bitewing',
          isActive: true,
        })
      ).rejects.toThrow('Creation failed');
    });

    it('getTemplate returns a single template', async () => {
      const tpl = { id: 'tpl-1', name: 'Default', isActive: true, createdAt: '', updatedAt: '' };
      server.use(
        http.get('/api/v1/imaging/templates/tpl-1', () => HttpResponse.json(tpl)),
      );
      const result = await imagingApi.getTemplate('tpl-1');
      expect(result).toEqual(tpl);
    });

    it('updateTemplate sends a PUT and returns updated template', async () => {
      const tpl = { id: 'tpl-1', name: 'Default', isActive: true, createdAt: '', updatedAt: '' };
      server.use(
        http.put('/api/v1/imaging/templates/tpl-1', async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...tpl, ...body });
        }),
      );
      const result = await imagingApi.updateTemplate('tpl-1', { name: 'Updated Name' });
      expect(result.name).toBe('Updated Name');
    });

    it('updateTemplate throws error on failure', async () => {
      server.use(
        http.put('/api/v1/imaging/templates/tpl-1', () =>
          HttpResponse.json({ message: 'Update failed' }, { status: 400 }),
        ),
      );
      await expect(
        imagingApi.updateTemplate('tpl-1', { name: 'Updated' })
      ).rejects.toThrow('Update failed');
    });

    it('deleteTemplate resolves', async () => {
      server.use(
        http.delete('/api/v1/imaging/templates/tpl-1', () =>
          HttpResponse.json({ message: 'Deleted' }),
        ),
      );
      await expect(imagingApi.deleteTemplate('tpl-1')).resolves.toBeUndefined();
    });
  });

  describe('summary', () => {
    it('getSummary returns aggregated stats', async () => {
      server.use(
        http.get('/api/v1/imaging/summary', () =>
          HttpResponse.json({
            totalImages: 100,
            totalSeries: 12,
            totalSize: 1234567,
            imagesThisMonth: 5,
          }),
        ),
      );
      const result = await imagingApi.getSummary();
      expect(result.totalImages).toBe(100);
    });
  });

  describe('utilities', () => {
    it('getImageUrl returns the file URL', () => {
      expect(imagingApi.getImageUrl(mockImage)).toBe('https://example.com/xray.png');
    });

    it('getThumbnailUrl returns the thumbnail when present', () => {
      expect(imagingApi.getThumbnailUrl(mockImage)).toBe('https://example.com/xray-thumb.png');
    });

    it('getThumbnailUrl falls back to fileUrl', () => {
      const noThumb = { ...mockImage, thumbnailUrl: undefined as unknown as string };
      expect(imagingApi.getThumbnailUrl(noThumb)).toBe(mockImage.fileUrl);
    });

    it('formatFileSize formats bytes', () => {
      expect(imagingApi.formatFileSize(0)).toBe('0 Bytes');
      expect(imagingApi.formatFileSize(1024)).toBe('1 KB');
      expect(imagingApi.formatFileSize(1024 * 1024)).toBe('1 MB');
      expect(imagingApi.formatFileSize(1024 * 1024 * 1024)).toBe('1 GB');
    });
  });
});
