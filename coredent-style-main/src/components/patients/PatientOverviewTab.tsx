import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Plus,
  User,
  AlertTriangle,
  StickyNote,
} from 'lucide-react';
import type { PatientRecord } from '@/types/patient';

interface PatientOverviewTabProps {
  patient: PatientRecord;
  onAddNote: () => void;
}

export function PatientOverviewTab({
  patient,
  onAddNote,
}: PatientOverviewTabProps) {
  const getNoteBadgeColor = (type: string) => {
    switch (type) {
      case 'clinical':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'billing':
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'alert':
        return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
      case 'communication':
        return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
      default:
        return 'bg-neutral-500/10 text-neutral-500 border-neutral-500/20';
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Contact & Personal details */}
      <div className="lg:col-span-1 space-y-6">
        <Card className="border border-border bg-card/60 backdrop-blur-md">
          <CardHeader>
            <CardTitle className="text-lg">Personal Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="space-y-1">
              <span className="block text-xs text-muted-foreground uppercase tracking-wider">Full Name</span>
              <span className="font-semibold text-foreground">{patient.firstName} {patient.lastName}</span>
            </div>

            <div className="space-y-1">
              <span className="block text-xs text-muted-foreground uppercase tracking-wider">Date of Birth</span>
              <span className="font-semibold text-foreground">{patient.dateOfBirth}</span>
            </div>

            <div className="space-y-1">
              <span className="block text-xs text-muted-foreground uppercase tracking-wider">Gender</span>
              <span className="font-semibold text-foreground capitalize">{patient.gender}</span>
            </div>

            {patient.address && (
              <div className="space-y-1">
                <span className="block text-xs text-muted-foreground uppercase tracking-wider">Home Address</span>
                <span className="font-semibold text-foreground">
                  {patient.address.street}, {patient.address.city}, {patient.address.state} {patient.address.zipCode}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Emergency Contact */}
        <Card className="border border-border bg-card/60 backdrop-blur-md">
          <CardHeader>
            <CardTitle className="text-lg">Emergency Contact</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {patient.emergencyContact ? (
              <>
                <div className="space-y-1">
                  <span className="block text-xs text-muted-foreground uppercase tracking-wider">Contact Name</span>
                  <span className="font-semibold text-foreground">
                    {patient.emergencyContact.name} ({patient.emergencyContact.relationship})
                  </span>
                </div>
                <div className="space-y-1">
                  <span className="block text-xs text-muted-foreground uppercase tracking-wider">Phone</span>
                  <span className="font-semibold text-foreground">{patient.emergencyContact.phone}</span>
                </div>
              </>
            ) : (
              <span className="text-muted-foreground italic text-xs">No emergency contact provided</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Timeline Notes */}
      <div className="lg:col-span-2 space-y-6">
        <Card className="border border-border bg-card/60 backdrop-blur-md">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Patient Notes & Timeline</CardTitle>
              <CardDescription>Clinical records, flags, and communications history</CardDescription>
            </div>
            <Button size="sm" onClick={onAddNote} className="gap-1">
              <Plus className="h-4 w-4" /> Add Note
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {patient.notes && patient.notes.length > 0 ? (
              <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
                {patient.notes.map((note) => (
                  <div key={note.id} className="rounded-xl border border-border bg-accent/20 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className={`${getNoteBadgeColor(note.type)} border text-xs capitalize`}>
                          {note.type}
                        </Badge>
                        {note.isAlert && (
                          <Badge variant="destructive" className="text-[10px] uppercase font-bold flex items-center gap-1">
                            <AlertTriangle className="h-3 w-3" /> Alert
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">{note.createdAt}</span>
                    </div>

                    <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                      {note.content}
                    </p>

                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground border-t border-border/40 pt-2">
                      <User className="h-3 w-3" />
                      <span>Recorded by {note.createdByName || note.createdBy}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border/80 p-8 text-center text-sm text-muted-foreground bg-accent/5">
                <StickyNote className="h-10 w-10 mx-auto opacity-40 mb-3 text-muted-foreground" />
                <p className="font-medium">No notes recorded yet</p>
                <p className="text-xs mt-1">Add general memos or clinical notifications to patient timeline.</p>
                <Button size="sm" variant="outline" onClick={onAddNote} className="mt-4 border-dashed border-primary/40 text-primary hover:bg-primary/5 hover:border-primary">
                  Record First Note
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
