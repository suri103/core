/**
 * Lab Management Page
 * Case tracking, lab vendor directory, and lab invoicing.
 *
 * Backed by the labs API: cases (list/create/update/delete), vendor
 * directory (list/create), and lab invoices (list). Summary cards and all
 * tables derive from real fetched data; empty states are explicit.
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
import { Plus, Beaker, Clock, CheckCircle, DollarSign, Pencil, Trash2 } from "lucide-react";
import { labsApi, type LabCaseRecord, type LabVendor, type LabInvoiceRecord } from "@/services/labsApi";
import { NewLabCaseDialog } from "@/components/lab/NewLabCaseDialog";
import { NewLabVendorDialog } from "@/components/lab/NewLabVendorDialog";
import { LabInvoiceDialog } from "@/components/lab/LabInvoiceDialog";

const CASE_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  sent: "Sent",
  in_progress: "In Progress",
  quality_check: "Quality Check",
  ready_to_ship: "Ready to Ship",
  shipped: "Shipped",
  delivered: "Delivered",
  completed: "Completed",
  on_hold: "On Hold",
  cancelled: "Cancelled",
  refused: "Refused",
};

const INVOICE_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  paid: "Paid",
  partial: "Partially Paid",
  overdue: "Overdue",
  cancelled: "Cancelled",
};

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

function labNameById(vendors: LabVendor[], id?: string): string {
  if (!id) return "—";
  return vendors.find((v) => v.id === id)?.name ?? "—";
}

export default function LabManagement() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [caseDialogOpen, setCaseDialogOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<LabCaseRecord | null>(null);
  const [vendorDialogOpen, setVendorDialogOpen] = useState(false);
  const [editingVendor, setEditingVendor] = useState<LabVendor | null>(null);
  const [deleteCase, setDeleteCase] = useState<LabCaseRecord | null>(null);
  const [deleteVendor, setDeleteVendor] = useState<LabVendor | null>(null);
  const [invoiceCreateOpen, setInvoiceCreateOpen] = useState(false);
  const [invoicePayOpen, setInvoicePayOpen] = useState(false);
  const [payingInvoice, setPayingInvoice] = useState<LabInvoiceRecord | null>(null);

  const casesQuery = useQuery({ queryKey: ["lab-cases"], queryFn: () => labsApi.listCases() });
  const vendorsQuery = useQuery({ queryKey: ["lab-vendors"], queryFn: () => labsApi.listVendors() });
  const invoicesQuery = useQuery({ queryKey: ["lab-invoices"], queryFn: () => labsApi.listInvoices() });

  const cases = casesQuery.data?.cases ?? [];
  const vendors = vendorsQuery.data?.labs ?? [];
  const invoices = invoicesQuery.data?.invoices ?? [];

  const active = cases.filter(
    (c) => !["completed", "cancelled", "refused"].includes((c.status ?? "").toLowerCase()),
  ).length;
  const completed = cases.filter(
    (c) => (c.status ?? "").toLowerCase() === "completed",
  ).length;
  const pending = cases.filter(
    (c) => (c.status ?? "").toLowerCase() === "pending",
  ).length;
  const labCost = invoices.reduce((sum, inv) => sum + (Number(inv.total ?? 0) || 0), 0);

  const refreshCases = () => {
    queryClient.invalidateQueries({ queryKey: ["lab-cases"] });
  };

  const openNewCase = () => {
    setEditingCase(null);
    setCaseDialogOpen(true);
  };
  const openEditCase = (c: LabCaseRecord) => {
    setEditingCase(c);
    setCaseDialogOpen(true);
  };

  const handleCaseSubmit = async (data: {
    lab_id: string;
    patient_id: string;
    case_type?: string;
    status?: string;
    description?: string;
    shade?: string;
    teeth_involved?: string;
    sent_date?: string;
    due_date?: string;
    provider_notes?: string;
  }): Promise<boolean> => {
    try {
      if (editingCase) {
        await labsApi.updateCase(editingCase.id, data);
        toast({ title: "Lab case updated" });
      } else {
        await labsApi.createCase(data);
        toast({ title: "Lab case created" });
      }
      refreshCases();
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not save the lab case. Please try again.",
        variant: "destructive",
      });
      return false;
    }
  };

  const confirmDeleteCase = async () => {
    if (!deleteCase) return;
    try {
      await labsApi.deleteCase(deleteCase.id);
      toast({ title: "Lab case deleted" });
      refreshCases();
    } catch {
      toast({
        title: "Error",
        description: "Could not delete the lab case.",
        variant: "destructive",
      });
    } finally {
      setDeleteCase(null);
    }
  };

  const handleVendorSubmit = async (data: Record<string, unknown>): Promise<boolean> => {
    try {
      if (editingVendor) {
        await labsApi.updateVendor(editingVendor.id, data);
        toast({ title: "Lab updated" });
      } else {
        await labsApi.createVendor(data);
        toast({ title: "Lab added" });
      }
      queryClient.invalidateQueries({ queryKey: ["lab-vendors"] });
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not save the lab vendor.",
        variant: "destructive",
      });
      return false;
    }
  };

  const confirmDeleteVendor = async () => {
    if (!deleteVendor) return;
    try {
      await labsApi.deleteVendor(deleteVendor.id);
      toast({ title: "Lab deleted" });
      queryClient.invalidateQueries({ queryKey: ["lab-vendors"] });
    } catch {
      toast({
        title: "Error",
        description: "Could not delete the lab vendor.",
        variant: "destructive",
      });
    } finally {
      setDeleteVendor(null);
    }
  };

  const handleInvoiceCreate = async (data: Record<string, unknown>): Promise<boolean> => {
    try {
      await labsApi.createInvoice(data);
      toast({ title: "Lab invoice created" });
      queryClient.invalidateQueries({ queryKey: ["lab-invoices"] });
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not create the lab invoice.",
        variant: "destructive",
      });
      return false;
    }
  };

  const handleInvoicePay = async (inv: LabInvoiceRecord) => {
    setPayingInvoice(inv);
    setInvoicePayOpen(true);
  };

  const handleInvoicePaySubmit = async (data: {
    amount: number;
    transaction_id: string;
    notes?: string;
  }): Promise<boolean> => {
    if (!payingInvoice?.id) return false;
    try {
      await labsApi.payInvoice(payingInvoice.id, data);
      toast({ title: "Payment recorded" });
      queryClient.invalidateQueries({ queryKey: ["lab-invoices"] });
      return true;
    } catch {
      toast({
        title: "Error",
        description: "Could not record the payment.",
        variant: "destructive",
      });
      return false;
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Lab Management</h1>
          <p className="text-muted-foreground">Track lab cases, vendors, and invoices</p>
        </div>
        <Button onClick={openNewCase}>
          <Plus className="mr-2 h-4 w-4" />
          New Case
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Cases</CardTitle>
            <Beaker className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{active}</div>
            <p className="text-xs text-muted-foreground">in progress</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-500">{pending}</div>
            <p className="text-xs text-muted-foreground">awaiting send</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">{completed}</div>
            <p className="text-xs text-muted-foreground">completed</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Lab Costs</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{labCost > 0 ? formatMoney(labCost) : "—"}</div>
            <p className="text-xs text-muted-foreground">from lab invoices</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="cases">
        <TabsList>
          <TabsTrigger value="cases">Cases</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
          <TabsTrigger value="labs">Labs</TabsTrigger>
        </TabsList>

        <TabsContent value="cases">
          <Card>
            <CardContent className="p-0">
              {casesQuery.isLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading cases…</div>
              ) : casesQuery.error ? (
                <div className="p-6 text-center text-muted-foreground">Unable to load lab cases.</div>
              ) : cases.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">No lab cases yet.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Case #</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Sent Date</TableHead>
                      <TableHead>Due Date</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cases.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium">{c.case_number ?? "—"}</TableCell>
                        <TableCell>
                          {c.case_type ? <Badge variant="outline">{c.case_type}</Badge> : "—"}
                        </TableCell>
                        <TableCell>{formatDate(c.sent_date)}</TableCell>
                        <TableCell>{formatDate(c.due_date)}</TableCell>
                        <TableCell>
                          {c.status ? <Badge>{CASE_STATUS_LABEL[c.status] ?? c.status}</Badge> : "—"}
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap">
                          <Button variant="ghost" size="sm" onClick={() => openEditCase(c)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteCase(c)}>
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

        <TabsContent value="invoices">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium">Lab Invoices</CardTitle>
                <Button size="sm" onClick={() => setInvoiceCreateOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Invoice
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {invoicesQuery.isLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading invoices…</div>
              ) : invoicesQuery.error ? (
                <div className="p-6 text-center text-muted-foreground">Unable to load lab invoices.</div>
              ) : invoices.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">No lab invoices yet.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Invoice #</TableHead>
                      <TableHead>Lab</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Balance</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invoices.map((inv) => (
                      <TableRow key={inv.id ?? inv.invoice_number ?? "inv"}>
                        <TableCell className="font-medium">{inv.invoice_number ?? "—"}</TableCell>
                        <TableCell>{labNameById(vendors, inv.lab_id)}</TableCell>
                        <TableCell>{formatDate(inv.invoice_date)}</TableCell>
                        <TableCell>{formatMoney(inv.total)}</TableCell>
                        <TableCell>
                          {formatMoney((Number(inv.total ?? 0) || 0) - (Number(inv.amount_paid ?? 0) || 0))}
                        </TableCell>
                        <TableCell>
                          {inv.status ? <Badge>{INVOICE_STATUS_LABEL[inv.status] ?? inv.status}</Badge> : "—"}
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap">
                          {inv.status !== "paid" && (
                            <Button variant="outline" size="sm" onClick={() => handleInvoicePay(inv)}>
                              Pay
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="labs">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium">Lab Vendors</CardTitle>
                <Button size="sm" onClick={() => { setEditingVendor(null); setVendorDialogOpen(true); }}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Lab
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {vendorsQuery.isLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading labs…</div>
              ) : vendorsQuery.error ? (
                <div className="p-6 text-center text-muted-foreground">Unable to load labs.</div>
              ) : vendors.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">No labs configured yet.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Lab Name</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Phone</TableHead>
                      <TableHead>City</TableHead>
                      <TableHead>Preferred</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendors.map((v) => (
                      <TableRow key={v.id}>
                        <TableCell className="font-medium">{v.name}</TableCell>
                        <TableCell>{v.contact_name ?? "—"}</TableCell>
                        <TableCell>{v.phone ?? "—"}</TableCell>
                        <TableCell>{[v.city, v.state].filter(Boolean).join(", ") || "—"}</TableCell>
                        <TableCell>
                          {v.is_preferred ? <Badge className="bg-green-500">Yes</Badge> : "No"}
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap">
                          <Button variant="ghost" size="sm" onClick={() => { setEditingVendor(v); setVendorDialogOpen(true); }}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteVendor(v)}>
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

      <NewLabCaseDialog
        open={caseDialogOpen}
        onOpenChange={setCaseDialogOpen}
        labs={vendors}
        initial={editingCase}
        onSubmit={handleCaseSubmit}
      />
      <NewLabVendorDialog
        open={vendorDialogOpen}
        onOpenChange={setVendorDialogOpen}
        initial={editingVendor}
        onSubmit={handleVendorSubmit}
      />
      <LabInvoiceDialog
        mode="create"
        open={invoiceCreateOpen}
        onOpenChange={setInvoiceCreateOpen}
        labs={vendors}
        onSubmit={handleInvoiceCreate}
      />
      <LabInvoiceDialog
        mode="pay"
        open={invoicePayOpen}
        onOpenChange={setInvoicePayOpen}
        invoice={payingInvoice ?? {}}
        onSubmit={handleInvoicePaySubmit}
      />

      <AlertDialog open={!!deleteCase} onOpenChange={(o) => !o && setDeleteCase(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete lab case?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-delete the lab case and remove it from active tracking.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteCase}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!deleteVendor} onOpenChange={(o) => !o && setDeleteVendor(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete lab vendor?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-delete the lab vendor. Existing case attribution is preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteVendor}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
