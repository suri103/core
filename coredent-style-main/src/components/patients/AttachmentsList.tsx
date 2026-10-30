import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { patientApi } from '@/services/patientApi';
import { sanitizeUrl } from '@/lib/sanitize';
import { 
  FileText, 
  Image as ImageIcon, 
  FileCheck, 
  Send, 
  File, 
  Download, 
  Trash2, 
  UploadCloud,
  Loader2
} from 'lucide-react';
import type { PatientAttachment } from '@/types/patient';

interface AttachmentsListProps {
  patientId: string;
  attachments: PatientAttachment[];
  onUpload: () => void;
  onDelete: () => void;
}

export function AttachmentsList({
  patientId,
  attachments,
  onUpload,
  onDelete,
}: AttachmentsListProps) {
  const { toast } = useToast();
  const [category, setCategory] = useState<PatientAttachment['category']>('other');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'insurance':
        return FileText;
      case 'xray':
        return ImageIcon;
      case 'consent':
        return FileCheck;
      case 'referral':
        return Send;
      default:
        return File;
    }
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (!bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      await patientApi.uploadAttachment(patientId, selectedFile, category);
      toast({
        title: 'File Uploaded',
        description: `${selectedFile.name} has been successfully added to record.`,
      });
      setSelectedFile(null);
      onUpload();
    } catch (err) {
      toast({
        title: 'Upload Failed',
        description: 'Failed to upload attachment.',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteAttachment = async (attachmentId: string, name: string) => {
    setIsDeleting(attachmentId);
    try {
      await patientApi.deleteAttachment(patientId, attachmentId);
      toast({
        title: 'File Deleted',
        description: `${name} has been deleted.`,
      });
      onDelete();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete file.',
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(null);
    }
  };

  const handleDownload = (url: string) => {
    const safeUrl = sanitizeUrl(url);
    if (!safeUrl) {
      toast({
        title: 'Invalid Document URL',
        description: 'The download link is malformed and cannot be opened.',
        variant: 'destructive',
      });
      return;
    }
    window.open(safeUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Upload card */}
      <div className="lg:col-span-1">
        <Card className="border border-border bg-card/60 backdrop-blur-md sticky top-6">
          <CardContent className="p-6">
            <h3 className="font-semibold text-lg text-foreground mb-4 flex items-center gap-2">
              <UploadCloud className="h-5 w-5 text-primary" />
              Upload Attachment
            </h3>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="attachCat">Document Category</Label>
                <Select value={category} onValueChange={(val) => setCategory(val as PatientAttachment['category'])}>
                  <SelectTrigger id="attachCat" className="bg-background/60 border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border">
                    <SelectItem value="insurance" className="cursor-pointer">Insurance Card</SelectItem>
                    <SelectItem value="xray" className="cursor-pointer">Dental X-Ray / Image</SelectItem>
                    <SelectItem value="consent" className="cursor-pointer">Signed Consent Form</SelectItem>
                    <SelectItem value="referral" className="cursor-pointer">Referral Note</SelectItem>
                    <SelectItem value="other" className="cursor-pointer">Other / Misc File</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="fileInput">Choose File</Label>
                <div className="flex items-center justify-center w-full">
                  <label 
                    htmlFor="fileInput" 
                    className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer bg-accent/5 border-border/80 hover:bg-accent/10 hover:border-primary/40 transition-colors"
                  >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                      <UploadCloud className="w-8 h-8 mb-2 text-muted-foreground/80" />
                      <p className="text-xs font-semibold text-muted-foreground">
                        {selectedFile ? selectedFile.name : 'Click to upload files'}
                      </p>
                      <p className="text-[10px] text-muted-foreground/60 mt-1">
                        {selectedFile ? `Size: ${formatBytes(selectedFile.size)}` : 'PDF, JPEG, PNG, DICOM up to 10MB'}
                      </p>
                    </div>
                    <input 
                      id="fileInput" 
                      type="file" 
                      className="hidden" 
                      onChange={handleFileChange}
                      required
                    />
                  </label>
                </div>
              </div>

              <Button
                type="submit"
                disabled={isUploading || !selectedFile}
                className="w-full font-semibold"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  'Upload to Patient Record'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Files List */}
      <div className="lg:col-span-2 space-y-4">
        <Card className="border border-border bg-card/60 backdrop-blur-md">
          <CardContent className="p-6">
            <h3 className="font-semibold text-lg text-foreground mb-4">Patient Document Repository</h3>

            {attachments && attachments.length > 0 ? (
              <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
                {attachments.map((file) => {
                  const Icon = getCategoryIcon(file.category);
                  return (
                    <div key={file.id} className="rounded-xl border border-border bg-accent/20 p-4 flex items-center justify-between gap-4 hover:border-primary/10 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 border border-primary/20 text-primary flex-shrink-0">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm text-foreground line-clamp-1">{file.name}</h4>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-[11px] text-muted-foreground">
                            <span className="capitalize">{file.category}</span>
                            <span className="h-1 w-1 rounded-full bg-border" />
                            <span>{formatBytes(file.size)}</span>
                            <span className="h-1 w-1 rounded-full bg-border" />
                            <span>Uploaded: {file.uploadedAt}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-1.5 flex-shrink-0">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          onClick={() => handleDownload(file.url)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={isDeleting === file.id}
                          className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDeleteAttachment(file.id, file.name)}
                        >
                          {isDeleting === file.id ? (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border/80 p-8 text-center text-sm text-muted-foreground bg-accent/5">
                <File className="h-10 w-10 mx-auto opacity-40 mb-3 text-muted-foreground" />
                <p className="font-medium">No documents uploaded yet</p>
                <p className="text-xs mt-1">Upload patient IDs, consent signatures, or diagnostic charts above.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
