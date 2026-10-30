/**
 * Referral Management Page
 * Patient referrals, specialist communication, and referral sources.
 *
 * Backed by the referrals API: list/create/update/delete referrals and
 * list/create referral sources. Summary cards and all tables derive from
 * real fetched data; empty states are explicit.
 */

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Plus, UserPlus, Clock, CheckCircle, DollarSign, Pencil, Trash2 } from "lucide-react";
import { referralsApi, type ReferralRecord, type ReferralSourceRecord } from "@/services/referralsApi";
import { NewReferralDialog } from "@/components/referrals/NewReferralDialog";
import { NewReferralSourceDialog } from "@/components/referrals/NewReferralSourceDialog";

function patientName(r: ReferralRecord): string {
  if (!r.patient) return "—";
  return `${r.patient.first_name ?? ""} ${r.patient.last_name ?? ""}`.trim() || "—";
}

function formatDate(value?: string): string {
  if (!value) return "—";
  const d = new Date(value);
  return isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function formatMoney(value?: string | number): string {
  const n = Number(value ?? 0);
  if (isNaN(n)) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function ReferralTable({
  referrals,
  onEdit,
  onDelete,
}: {
  referrals: ReferralRecord[];
  onEdit: (r: ReferralRecord) => void;
  onDelete: (r: ReferralRecord) => void;
}) {
  if (referrals.length === 0) {
    return <CardContent className="p-6 text-center text-muted-foreground">No referrals yet.</CardContent>;
  }
  return (
    <CardContent className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Patient</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {referrals.map((r) => (
            <TableRow key={r.id}>
              <TableCell>{formatDate(r.referral_date)}</TableCell>
              <TableCell className="font-medium">{patientName(r)}</TableCell>
              <TableCell>
                {r.referral_type ? <Badge variant="outline">{r.referral_type}</Badge> : "—"}
              </TableCell>
              <TableCell>{r.status ? <Badge>{r.status}</Badge> : "—"}</TableCell>
              <TableCell className="text-right whitespace-nowrap">
                <Button variant="ghost" size="sm" onClick={() => onEdit(r)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => onDelete(r)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </CardContent>
  );
}

export default function Referrals() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [referralDialogOpen, setReferralDialogOpen] = useState(false);
  const [editingReferral, setEditingReferral] = useState<ReferralRecord | null>(null);
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<ReferralSourceRecord | null>(null);
  const [deleteReferral, setDeleteReferral] = useState<ReferralRecord | null>(null);
  const [deleteSource, setDeleteSource] = useState<ReferralSourceRecord | null>(null);

  const referralsQuery = useQuery({ queryKey: ["referrals"], queryFn: () => referralsApi.list() });
  const sourcesQuery = useQuery({
    queryKey: ["referral-sources"],
    queryFn: () => referralsApi.listSources(),
  });

  const referrals = referralsQuery.data?.referrals ?? [];
  const sources = sourcesQuery.data?.sources ?? [];

  const pending = referrals.filter((r) => (r.status ?? "").toLowerCase() === "pending");
  const completed = referrals.filter((r) => (r.status ?? "").toLowerCase() === "completed");
  const totalFees = referrals.reduce((sum, r) => sum + (Number(r.referral_fee ?? 0) || 0), 0);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["referrals"] });

  const openNewReferral = () => {
    setEditingReferral(null);
    setReferralDialogOpen(true);
  };
  const openEditReferral = (r: ReferralRecord) => {
    setEditingReferral(r);
    setReferralDialogOpen(true);
  };

  const handleReferralSubmit = async (data: Record<string, unknown>): Promise<boolean> => {
    try {
      if (editingReferral) {
        await referralsApi.update(editingReferral.id, data);
        toast({ title: "Referral updated" });
      } else {
        await referralsApi.create(data);
        toast({ title: "Referral created" });
      }
      refresh();
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not save the referral. Please try again.",
        variant: "destructive",
      });
      return false;
    }
  };

  const confirmDeleteReferral = async () => {
    if (!deleteReferral) return;
    try {
      await referralsApi.remove(deleteReferral.id);
      toast({ title: "Referral deleted" });
      refresh();
    } catch {
      toast({
        title: "Error",
        description: "Could not delete the referral.",
        variant: "destructive",
      });
    } finally {
      setDeleteReferral(null);
    }
  };

  const handleSourceSubmit = async (data: Record<string, unknown>): Promise<boolean> => {
    try {
      if (editingSource) {
        await referralsApi.updateSource(editingSource.id, data);
        toast({ title: "Referral source updated" });
      } else {
        await referralsApi.createSource(data);
        toast({ title: "Referral source added" });
      }
      queryClient.invalidateQueries({ queryKey: ["referral-sources"] });
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not save the referral source.",
        variant: "destructive",
      });
      return false;
    }
  };

  const confirmDeleteSource = async () => {
    if (!deleteSource) return;
    try {
      await referralsApi.removeSource(deleteSource.id);
      toast({ title: "Referral source deleted" });
      queryClient.invalidateQueries({ queryKey: ["referral-sources"] });
    } catch {
      toast({
        title: "Error",
        description: "Could not delete the referral source.",
        variant: "destructive",
      });
    } finally {
      setDeleteSource(null);
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Referral Management</h1>
          <p className="text-muted-foreground">Track patient referrals and specialist communications</p>
        </div>
        <Button onClick={openNewReferral}>
          <Plus className="mr-2 h-4 w-4" />
          New Referral
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Referrals</CardTitle>
            <UserPlus className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{referrals.length}</div>
            <p className="text-xs text-muted-foreground">this quarter</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-500">{pending.length}</div>
            <p className="text-xs text-muted-foreground">awaiting appointment</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">{completed.length}</div>
            <p className="text-xs text-muted-foreground">completed</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Referral Fees</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalFees > 0 ? formatMoney(totalFees) : "—"}</div>
            <p className="text-xs text-muted-foreground">total referral fees</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <Card>
            {referralsQuery.isLoading ? (
              <CardContent className="p-6 text-center text-muted-foreground">Loading referrals…</CardContent>
            ) : referralsQuery.error ? (
              <CardContent className="p-6 text-center text-muted-foreground">Unable to load referrals.</CardContent>
            ) : (
              <ReferralTable
                referrals={referrals}
                onEdit={openEditReferral}
                onDelete={setDeleteReferral}
              />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="pending">
          <Card>
            {pending.length === 0 ? (
              <CardContent className="p-6 text-center text-muted-foreground">No pending referrals.</CardContent>
            ) : (
              <ReferralTable
                referrals={pending}
                onEdit={openEditReferral}
                onDelete={setDeleteReferral}
              />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="completed">
          <Card>
            {completed.length === 0 ? (
              <CardContent className="p-6 text-center text-muted-foreground">No completed referrals yet.</CardContent>
            ) : (
              <ReferralTable
                referrals={completed}
                onEdit={openEditReferral}
                onDelete={setDeleteReferral}
              />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="sources">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium">Referral Sources</CardTitle>
                <Button size="sm" onClick={() => { setEditingSource(null); setSourceDialogOpen(true); }}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Source
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {sourcesQuery.isLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading sources…</div>
              ) : sourcesQuery.error ? (
                <div className="p-6 text-center text-muted-foreground">Unable to load referral sources.</div>
              ) : sources.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">No referral sources yet.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Total Referrals</TableHead>
                      <TableHead>Active</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sources.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell>
                          {s.source_type ? <Badge variant="outline">{s.source_type}</Badge> : "—"}
                        </TableCell>
                        <TableCell>{s.contact_name ?? "—"}</TableCell>
                        <TableCell>{s.total_referrals ?? "0"}</TableCell>
                        <TableCell>
                          {s.is_active ? <Badge className="bg-green-500">Yes</Badge> : "No"}
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap">
                          <Button variant="ghost" size="sm" onClick={() => { setEditingSource(s); setSourceDialogOpen(true); }}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteSource(s)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <NewReferralDialog
        open={referralDialogOpen}
        onOpenChange={setReferralDialogOpen}
        initial={editingReferral}
        onSubmit={handleReferralSubmit}
      />
      <NewReferralSourceDialog
        open={sourceDialogOpen}
        onOpenChange={setSourceDialogOpen}
        initial={editingSource}
        onSubmit={handleSourceSubmit}
      />

      <AlertDialog open={!!deleteReferral} onOpenChange={(o) => !o && setDeleteReferral(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete referral?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-delete the referral. The clinical record is preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteReferral}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!deleteSource} onOpenChange={(o) => !o && setDeleteSource(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete referral source?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-delete the referral source. Past referral attribution is preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteSource}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
