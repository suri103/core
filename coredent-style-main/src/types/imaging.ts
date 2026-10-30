// ============================================
// CoreDent PMS - Imaging Types
// TypeScript types for imaging management
// ============================================

export type ImageType = 'xray' | 'photo' | 'scan' | 'document' | 'other';
export type ImageCategory = 'periapical' | 'bitewing' | 'panoramic' | 'cephalometric' | 'cbct' | 'intraoral' | 'extraoral' | 'other';

export interface PatientImage {
  id: string;
  patientId: string;
  patientName?: string;
  seriesId?: string;
  imageType: ImageType;
  category: ImageCategory;
  title: string;
  description?: string;
  toothNumber?: string;
  captureDate: string;
  fileUrl: string;
  thumbnailUrl?: string;
  fileSize: number;
  mimeType: string;
  width?: number;
  height?: number;
  annotations?: ImageAnnotation[];
  tags?: string[];
  isArchived: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface ImageAnnotation {
  id: string;
  type: 'arrow' | 'circle' | 'rectangle' | 'text' | 'freehand';
  x: number;
  y: number;
  width?: number;
  height?: number;
  text?: string;
  color: string;
  points?: { x: number; y: number }[];
}

export interface ImageSeries {
  id: string;
  patientId: string;
  patientName?: string;
  name: string;
  description?: string;
  seriesDate: string;
  imageCount: number;
  images?: PatientImage[];
  createdAt: string;
  updatedAt: string;
}

export interface ImageTemplate {
  id: string;
  name: string;
  description?: string;
  imageType: ImageType;
  category: ImageCategory;
  defaultTags?: string[];
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ImagingSummary {
  totalImages: number;
  imagesByType: Record<ImageType, number>;
  imagesByCategory: Record<ImageCategory, number>;
  totalSeries: number;
  storageUsed: number;
  recentImages: PatientImage[];
}
