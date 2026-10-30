// ============================================
// CoreDent PMS - Imaging API Service
// API calls for imaging management
// ============================================

import type {
  PatientImage,
  ImageSeries,
  ImageTemplate,
  ImagingSummary,
  ImageType,
  ImageCategory,
  ImageAnnotation,
} from '@/types/imaging';
import { apiClient } from './api';
import { requireApiData, requireApiSuccess } from './apiResponse';
type BackendImage = Record<string, unknown>;

function normalizeImage(raw: BackendImage): PatientImage {
  const annotations = raw.annotations;
  let normalizedAnnotations: ImageAnnotation[] = [];
  if (Array.isArray(annotations)) normalizedAnnotations = annotations as ImageAnnotation[];
  if (typeof annotations === 'string') {
    try { normalizedAnnotations = JSON.parse(annotations) as ImageAnnotation[]; } catch { normalizedAnnotations = []; }
  }
  return {
    id: String(raw.id ?? ''),
    patientId: String(raw.patientId ?? raw.patient_id ?? ''),
    seriesId: raw.seriesId ? String(raw.seriesId) : raw.series_id ? String(raw.series_id) : undefined,
    imageType: (raw.imageType ?? raw.image_type ?? 'other') as ImageType,
    category: (raw.category ?? 'other') as ImageCategory,
    title: String(raw.title ?? raw.file_name ?? 'Image'),
    description: raw.description ? String(raw.description) : undefined,
    toothNumber: raw.toothNumber ? String(raw.toothNumber) : raw.tooth_number ? String(raw.tooth_number) : undefined,
    captureDate: String(raw.captureDate ?? raw.acquisition_date ?? raw.created_at ?? ''),
    fileUrl: String(raw.fileUrl ?? raw.url ?? raw.file_path ?? ''),
    thumbnailUrl: raw.thumbnailUrl ? String(raw.thumbnailUrl) : undefined,
    fileSize: Number(raw.fileSize ?? raw.file_size ?? 0),
    mimeType: String(raw.mimeType ?? raw.mime_type ?? 'application/octet-stream'),
    width: raw.width ? Number(raw.width) : undefined,
    height: raw.height ? Number(raw.height) : undefined,
    annotations: normalizedAnnotations,
    tags: Array.isArray(raw.tags) ? raw.tags as string[] : [],
    isArchived: Boolean(raw.isArchived ?? raw.is_deleted ?? false),
    createdBy: String(raw.createdBy ?? raw.provider_id ?? ''),
    createdAt: String(raw.createdAt ?? raw.created_at ?? ''),
    updatedAt: String(raw.updatedAt ?? raw.updated_at ?? ''),
  };
}

export const imagingApi = {
  // ============================================
  // Patient Images
  // ============================================

  async getImages(filters?: {
    patientId?: string;
    imageType?: ImageType;
    category?: ImageCategory;
    toothNumber?: string;
    startDate?: string;
    endDate?: string;
  }): Promise<PatientImage[]> {
    const { patientId, imageType, category, toothNumber, startDate, endDate } = filters ?? {};
    const response = patientId
      ? await apiClient.get<PatientImage[] | { images: PatientImage[] }>(
          `/imaging/patients/${encodeURIComponent(patientId)}/images`,
          { image_type: imageType, category, tooth_number: toothNumber, start_date: startDate, end_date: endDate },
        )
      : await apiClient.get<PatientImage[]>('/imaging/images');
    const payload = requireApiData(response, 'Failed to load images');
    const images = Array.isArray(payload) ? payload : payload.images;
    return images.map((image) => normalizeImage(image as unknown as BackendImage));
  },
  async getImage(imageId: string): Promise<PatientImage | null> {
    return requireApiData(
      await apiClient.get<PatientImage>(`/imaging/images/${imageId}`),
      'Failed to load image',
    );
  },

  async uploadImage(data: {
    patientId: string;
    file: File;
    imageType: ImageType;
    category?: ImageCategory;
    title?: string;
    description?: string;
    notes?: string;
    toothNumber?: string;
    deviceName?: string;
    deviceSerial?: string;
  }): Promise<PatientImage> {
    // Backend contract (endpoints/imaging.py upload_image): multipart `file`
    // plus snake_case QUERY parameters — metadata sent as form fields 404s.
    const params = new URLSearchParams();
    params.set('image_type', data.imageType);
    if (data.category) params.set('category', data.category);
    if (data.title) params.set('title', data.title);
    if (data.description) params.set('description', data.description);
    if (data.notes) params.set('notes', data.notes);
    if (data.toothNumber) params.set('tooth_number', data.toothNumber);
    if (data.deviceName) params.set('device_name', data.deviceName);
    if (data.deviceSerial) params.set('device_serial', data.deviceSerial);

    const formData = new FormData();
    formData.append('file', data.file);

    const response = await apiClient.post<PatientImage>(
      `/imaging/patients/${encodeURIComponent(data.patientId)}/images?${params.toString()}`,
      formData,
    );

    if (response.success && response.data) {
      return normalizeImage(response.data as unknown as BackendImage);
    }
    throw new Error(response.error?.message || 'Failed to upload image');
  },

  async updateImage(imageId: string, data: Partial<PatientImage>): Promise<PatientImage> {
    const response = await apiClient.put<PatientImage>(`/imaging/images/${imageId}`, data);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to update image');
  },

  async deleteImage(imageId: string): Promise<void> {
    requireApiSuccess(
      await apiClient.delete<void>(`/imaging/images/${imageId}`),
      'Failed to delete image',
    );
  },

  async addAnnotation(imageId: string, annotation: Omit<ImageAnnotation, 'id'>): Promise<PatientImage> {
    const response = await apiClient.post<PatientImage>(`/imaging/images/${imageId}/annotations`, annotation);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to add annotation');
  },

  async deleteAnnotation(imageId: string, annotationId: string): Promise<PatientImage> {
    const response = await apiClient.delete<PatientImage>(`/imaging/images/${imageId}/annotations/${annotationId}`);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to delete annotation');
  },

  // ============================================
  // Image Series
  // ============================================

  async getSeries(filters?: { patientId?: string }): Promise<ImageSeries[]> {
    const response = filters?.patientId
      ? await apiClient.get<ImageSeries[] | { series: ImageSeries[] }>(
          `/imaging/patients/${encodeURIComponent(filters.patientId)}/series`,
        )
      : await apiClient.get<ImageSeries[]>('/imaging/series');
    const payload = requireApiData(response, 'Failed to load image series');
    return Array.isArray(payload) ? payload : payload.series;
  },
  async getSeriesById(seriesId: string): Promise<ImageSeries | null> {
    return requireApiData(
      await apiClient.get<ImageSeries>(`/imaging/series/${seriesId}`),
      'Failed to load image series',
    );
  },

  async createSeries(data: {
    patientId: string;
    name: string;
    description?: string;
    seriesDate: string;
  }): Promise<ImageSeries> {
    const response = await apiClient.post<ImageSeries>('/imaging/series', data);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to create series');
  },

  async updateSeries(seriesId: string, data: Partial<ImageSeries>): Promise<ImageSeries> {
    const response = await apiClient.put<ImageSeries>(`/imaging/series/${seriesId}`, data);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to update series');
  },

  async deleteSeries(seriesId: string): Promise<void> {
    requireApiSuccess(
      await apiClient.delete<void>(`/imaging/series/${seriesId}`),
      'Failed to delete image series',
    );
  },

  // ============================================
  // Image Templates
  // ============================================

  async getTemplates(filters?: { isActive?: boolean }): Promise<ImageTemplate[]> {
    return requireApiData(
      await apiClient.get<ImageTemplate[]>('/imaging/templates', filters as Record<string, unknown>),
      'Failed to load image templates',
    );
  },

  async getTemplate(templateId: string): Promise<ImageTemplate | null> {
    return requireApiData(
      await apiClient.get<ImageTemplate>(`/imaging/templates/${templateId}`),
      'Failed to load image template',
    );
  },

  async createTemplate(data: Omit<ImageTemplate, 'id' | 'createdAt' | 'updatedAt'>): Promise<ImageTemplate> {
    const response = await apiClient.post<ImageTemplate>('/imaging/templates', data);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to create template');
  },

  async updateTemplate(templateId: string, data: Partial<ImageTemplate>): Promise<ImageTemplate> {
    const response = await apiClient.put<ImageTemplate>(`/imaging/templates/${templateId}`, data);
    if (response.success && response.data) {
      return response.data;
    }
    throw new Error(response.error?.message || 'Failed to update template');
  },

  async deleteTemplate(templateId: string): Promise<void> {
    requireApiSuccess(
      await apiClient.delete<void>(`/imaging/templates/${templateId}`),
      'Failed to delete image template',
    );
  },

  // ============================================
  // Summary & Reports
  // ============================================

  async getSummary(): Promise<ImagingSummary> {
    return requireApiData(
      await apiClient.get<ImagingSummary>('/imaging/summary'),
      'Failed to load imaging summary',
    );
  },

  // ============================================
  // Hardware Bridge / TWAIN Capture
  // ============================================

  async getBridgeDevices(): Promise<any[]> {
    const res = await apiClient.get<any[]>('/imaging/hardware-bridge/devices');
    return res.data || (res as any) || [];
  },

  async acquireSensorFrame(payload: {
    patient_id: string;
    tooth_number?: string;
    view_type?: string;
    sensor_model?: string;
    format?: string;
  }): Promise<any> {
    const res = await apiClient.post<any>('/imaging/hardware-bridge/acquire', payload);
    return res.data || (res as any);
  },

  // ============================================
  // Utility Functions
  // ============================================

  getImageUrl(image: PatientImage): string {
    return image.fileUrl;
  },

  getThumbnailUrl(image: PatientImage): string {
    return image.thumbnailUrl || image.fileUrl;
  },

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  },
};
