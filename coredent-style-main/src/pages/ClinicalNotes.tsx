import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { clinicalNotesApi, patientsApi } from '@/services/api';
import type { ClinicalNote, Patient } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Pencil, Trash2, Pill } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { logger } from '@/lib/logger';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { format } from 'date-fns';
import { EPrescribeModal } from '@/components/treatment/ePrescribeModal';

export default function ClinicalNotes() {
  const { id: patientId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const [notes, setNotes] = useState<ClinicalNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [patientLoading, setPatientLoading] = useState(false);
  const [patientError, setPatientError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<Patient[]>([]);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<ClinicalNote | null>(null);
  const [noteType, setNoteType] = useState<ClinicalNote['type']>('general');
  const [content, setContent] = useState('');
  const [subjective, setSubjective] = useState('');
  const [objective, setObjective] = useState('');
  const [assessment, setAssessment] = useState('');
  const [plan, setPlan] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isEPrescribeOpen, setIsEPrescribeOpen] = useState(false);

  useEffect(() => {
    if (patientId) {
      loadPatient(patientId);
      loadNotes(patientId);
    } else {
      setPatient(null);
      setNotes([]);
      setError(null);
      setPatientError(null);
    }
  }, [patientId]);

  const loadNotes = async (pid: string) => {
    setLoading(true);
    try {
      const response = await clinicalNotesApi.listByPatient(pid);
      if (response.success && response.data) {
        setNotes(response.data);
      } else {
        setError(response.error?.message || 'Failed to load notes');
      }
    } catch (err) {
      logger.error('Failed to load notes', err instanceof Error ? err : new Error(String(err)));
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const loadPatient = async (pid: string) => {
    setPatientLoading(true);
    setPatientError(null);
    try {
      const response = await patientsApi.getById(pid);
      if (response.success && response.data) {
        setPatient(response.data);
      } else {
        setPatientError(response.error?.message || 'Failed to load patient');
      }
    } catch (err) {
      logger.error('Failed to load patient', err instanceof Error ? err : new Error(String(err)));
      setPatientError('An unexpected error occurred');
    } finally {
      setPatientLoading(false);
    }
  };

  useEffect(() => {
    if (patientId) return;
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const response = await patientsApi.list({ search: searchQuery.trim(), limit: 8 });
        if (response.success && response.data) {
          const data = response.data as Patient[] | { data?: Patient[] };
          setSearchResults(Array.isArray(data) ? data : (data.data ?? []));
        } else {
          setSearchResults([]);
        }
      } catch (err) {
        logger.error('Patient search failed', err instanceof Error ? err : new Error(String(err)));
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [searchQuery, patientId]);

  const canSave = useMemo(() => {
    if (noteType === 'soap') {
      return (
        subjective.trim().length > 0 ||
        objective.trim().length > 0 ||
        assessment.trim().length > 0 ||
        plan.trim().length > 0
      );
    }
    return content.trim().length > 0;
  }, [noteType, subjective, objective, assessment, plan, content]);

  const resetForm = () => {
    setEditingNote(null);
    setNoteType('general');
    setContent('');
    setSubjective('');
    setObjective('');
    setAssessment('');
    setPlan('');
  };

  const handleEditClick = (note: ClinicalNote) => {
    setEditingNote(note);
    setNoteType(note.type);
    if (note.type === 'soap') {
      setSubjective(note.subjective || '');
      setObjective(note.objective || '');
      setAssessment(note.assessment || '');
      setPlan(note.plan || '');
      setContent('');
    } else {
      setContent(note.content || '');
      setSubjective('');
      setObjective('');
      setAssessment('');
      setPlan('');
    }
    setIsCreateOpen(true);
  };

  const handleSaveNote = async () => {
    if (!patientId || !canSave) return;
    setIsSaving(true);
    try {
      const payload: Omit<ClinicalNote, 'id' | 'createdAt' | 'updatedAt'> = {
        patientId,
        providerId: editingNote ? editingNote.providerId : user?.id || 'unknown',
        providerName: editingNote
          ? editingNote.providerName
          : user
            ? `${user.firstName} ${user.lastName}`
            : 'Unknown',
        type: noteType,
        subjective: noteType === 'soap' ? subjective.trim() || undefined : undefined,
        objective: noteType === 'soap' ? objective.trim() || undefined : undefined,
        assessment: noteType === 'soap' ? assessment.trim() || undefined : undefined,
        plan: noteType === 'soap' ? plan.trim() || undefined : undefined,
        content: noteType === 'soap' ? undefined : content.trim(),
      };

      if (editingNote) {
        const response = await clinicalNotesApi.update(editingNote.id, payload);
        if (response.success && response.data) {
          setNotes((prev) => prev.map((n) => (n.id === editingNote.id ? response.data! : n)));
          setIsCreateOpen(false);
          resetForm();
          toast({
            title: 'Note updated',
            description: 'Clinical note updated successfully',
          });
        } else {
          toast({
            title: 'Error',
            description: response.error?.message || 'Failed to update note',
            variant: 'destructive',
          });
        }
      } else {
        const response = await clinicalNotesApi.create(payload);
        if (response.success && response.data) {
          setNotes((prev) => [response.data!, ...prev]);
          setIsCreateOpen(false);
          resetForm();
          toast({
            title: 'Note created',
            description: 'Clinical note saved successfully',
          });
        } else {
          toast({
            title: 'Error',
            description: response.error?.message || 'Failed to create note',
            variant: 'destructive',
          });
        }
      }
    } catch (err) {
      logger.error('Failed to save note', err instanceof Error ? err : new Error(String(err)));
      toast({
        title: 'Error',
        description: 'Failed to save note',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteNote = async (id: string) => {
    try {
      const response = await clinicalNotesApi.delete(id);
      if (response.success) {
        setNotes((prev) => prev.filter((n) => n.id !== id));
        toast({
          title: 'Note deleted',
          description: 'Clinical note deleted successfully',
        });
      } else {
        toast({
          title: 'Error',
          description: response.error?.message || 'Failed to delete note',
          variant: 'destructive',
        });
      }
    } catch (err) {
      logger.error('Failed to delete note', err instanceof Error ? err : new Error(String(err)));
      toast({
        title: 'Error',
        description: 'Failed to delete note',
        variant: 'destructive',
      });
    }
  };

  if (!patientId) {
    return (
      <div className="container mx-auto p-6">
        <h1 className="mb-6 text-3xl font-bold">Clinical Notes</h1>
        <Card>
          <CardContent className="space-y-4 p-6">
            <div className="text-muted-foreground">
              Search for a patient to view their clinical notes.
            </div>
            <div className="flex gap-2">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name or email..."
              />
              <Button variant="outline" onClick={() => setSearchQuery('')}>
                Clear
              </Button>
            </div>
            {searchLoading ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : searchResults.length === 0 ? (
              <div className="text-sm text-muted-foreground">No matching patients.</div>
            ) : (
              <div className="space-y-2">
                {searchResults.map((result) => (
                  <Button
                    key={result.id}
                    variant="ghost"
                    className="w-full justify-start"
                    onClick={() => navigate(`/notes/${result.id}`)}
                  >
                    {result.firstName} {result.lastName} · {result.email}
                  </Button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Clinical Notes</h1>
          {patientLoading ? (
            <div className="text-sm text-muted-foreground">Loading patient...</div>
          ) : patient ? (
            <div className="text-sm text-muted-foreground">
              {patient.firstName} {patient.lastName}
            </div>
          ) : patientError ? (
            <div className="text-sm text-destructive">{patientError}</div>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setIsEPrescribeOpen(true)}>
            <Pill className="mr-2 h-4 w-4" />
            Write eRx
          </Button>
          <Button onClick={() => setIsCreateOpen(true)}>New Note</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <Card className="border-destructive">
          <CardContent className="p-6 text-destructive">{error}</CardContent>
        </Card>
      ) : notes.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            No clinical notes found for this patient.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {notes.map((note) => (
            <Card key={note.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-medium">
                      {format(new Date(note.createdAt), 'PPP p')}
                    </CardTitle>
                    <div className="text-sm text-muted-foreground">by {note.providerName}</div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={() => handleEditClick(note)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This will permanently delete this clinical note. This action cannot be
                            undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleDeleteNote(note.id)}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/95"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {note.type === 'soap' ? (
                  <div className="space-y-3">
                    {note.subjective && (
                      <div>
                        <div className="text-xs font-semibold text-muted-foreground">
                          Subjective
                        </div>
                        <div className="whitespace-pre-wrap">{note.subjective}</div>
                      </div>
                    )}
                    {note.objective && (
                      <div>
                        <div className="text-xs font-semibold text-muted-foreground">Objective</div>
                        <div className="whitespace-pre-wrap">{note.objective}</div>
                      </div>
                    )}
                    {note.assessment && (
                      <div>
                        <div className="text-xs font-semibold text-muted-foreground">
                          Assessment
                        </div>
                        <div className="whitespace-pre-wrap">{note.assessment}</div>
                      </div>
                    )}
                    {note.plan && (
                      <div>
                        <div className="text-xs font-semibold text-muted-foreground">Plan</div>
                        <div className="whitespace-pre-wrap">{note.plan}</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{note.content}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          setIsCreateOpen(open);
          if (!open) resetForm();
        }}
      >
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>{editingNote ? 'Edit Clinical Note' : 'New Clinical Note'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Note Type</Label>
              <Select
                value={noteType}
                onValueChange={(v) => setNoteType(v as ClinicalNote['type'])}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="general">General</SelectItem>
                  <SelectItem value="procedure">Procedure</SelectItem>
                  <SelectItem value="soap">SOAP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {noteType === 'soap' ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Subjective</Label>
                  <Textarea
                    value={subjective}
                    onChange={(e) => setSubjective(e.target.value)}
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Objective</Label>
                  <Textarea
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Assessment</Label>
                  <Textarea
                    value={assessment}
                    onChange={(e) => setAssessment(e.target.value)}
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Plan</Label>
                  <Textarea value={plan} onChange={(e) => setPlan(e.target.value)} rows={4} />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Note</Label>
                <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveNote} disabled={!canSave || isSaving}>
              {isSaving ? 'Saving...' : editingNote ? 'Update Note' : 'Save Note'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <EPrescribeModal
        isOpen={isEPrescribeOpen}
        onClose={() => setIsEPrescribeOpen(false)}
        patientId={patient?.id || ''}
        patientName={patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown Patient'}
      />
    </div>
  );
}
