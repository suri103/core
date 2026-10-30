import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Plus, Eye, Download, Image as ImageIcon } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { imagingApi } from '@/services/imagingApi';
import type { PatientImage } from '@/types/imaging';

interface ImageGalleryProps {
  patientId?: string;
  onImageSelect?: (image: PatientImage) => void;
  onUpload?: () => void;
}

export function ImageGallery({ patientId, onImageSelect, onUpload }: ImageGalleryProps) {
  const { toast } = useToast();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedImage, setSelectedImage] = useState<PatientImage | null>(null);

  const { data: images, isLoading, error } = useQuery({
    queryKey: ['patient-images', patientId],
    queryFn: () => imagingApi.getImages({ patientId: patientId! }),
    enabled: !!patientId,
  });

  const handleImageSelect = (image: PatientImage) => {
    setSelectedImage(image);
    if (onImageSelect) onImageSelect(image);
  };

  const handleDownload = async (image: PatientImage) => {
    try {
      const link = document.createElement('a');
      link.href = image.fileUrl;
      link.download = image.title || `image_${image.id}`;
      link.target = '_blank';
      link.click();
      toast({
        title: 'Success',
        description: 'Image download started',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to download image',
        variant: 'destructive',
      });
    }
  };

  const formatFileSize = (bytes: number): string => {
    return imagingApi.formatFileSize(bytes);
  };

  const filteredImages = images?.filter(image =>
    image.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    image.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    image.imageType.toLowerCase().includes(searchTerm.toLowerCase()) ||
    image.category.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  if (!patientId) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Please select a patient to view their imaging
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-red-500">
          Failed to load patient images
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <CardTitle>Patient Images</CardTitle>
          <p className="text-sm text-muted-foreground">
            View and manage patient imaging files
          </p>
        </div>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search images..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button onClick={() => onUpload?.()}>
            <Plus className="mr-2 h-4 w-4" />
            Upload
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {filteredImages.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {searchTerm ? 'No images found matching your search' : 'No images uploaded yet'}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredImages.map((image) => (
              <div
                key={image.id}
                className={`border rounded-lg p-4 hover:bg-muted/50 transition-colors cursor-pointer ${
                  selectedImage?.id === image.id ? 'ring-2 ring-primary' : ''
                }`}
                onClick={() => handleImageSelect(image)}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-muted rounded">
                    <ImageIcon className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium truncate">{image.title}</h4>
                    <p className="text-sm text-muted-foreground">
                      {image.imageType} - {image.category}
                    </p>
                  </div>
                  <Badge variant="outline">{formatFileSize(image.fileSize)}</Badge>
                </div>
                {image.description && (
                  <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                    {image.description}
                  </p>
                )}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownload(image);
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleImageSelect(image);
                    }}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    View
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}