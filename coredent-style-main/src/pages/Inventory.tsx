/**
 * Live inventory management.
 *
 * Quantities, alerts, and stock movements are read from and written to the
 * tenant-scoped inventory API. No sample quantities or inert production
 * actions are rendered here.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowDown, ArrowUp, Boxes, Edit3, Package, Plus, Search, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { inventoryApi, type InventoryCategory, type InventoryItem, type InventoryItemWrite, type InventoryTransactionType, type InventoryUnit } from '@/services/inventoryApi';
import type { ApiResponse } from '@/types/api';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';

const categories: InventoryCategory[] = ['supplies', 'equipment', 'medications', 'restorative', 'surgical', 'disposable', 'other'];
const units: InventoryUnit[] = ['each', 'box', 'pack', 'case', 'gallon', 'liter'];

type ItemFormState = {
  name: string;
  sku: string;
  category: InventoryCategory;
  unit: InventoryUnit;
  current_quantity: string;
  minimum_quantity: string;
  reorder_quantity: string;
};

const emptyItemForm: ItemFormState = {
  name: '',
  sku: '',
  category: 'supplies',
  unit: 'each',
  current_quantity: '0',
  minimum_quantity: '0',
  reorder_quantity: '0',
};

async function requireData<T>(response: ApiResponse<T>): Promise<T> {
  if (!response.success || response.data === undefined) {
    throw new Error(response.error?.message || 'The inventory service did not return data.');
  }
  return response.data;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The inventory service is temporarily unavailable.';
}

function displayLabel(value: string): string {
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

export default function Inventory() {
  const { toast } = useToast();
  const { hasRole } = useAuth();
  const canManageInventory = hasRole('owner', 'admin');
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [itemDialogOpen, setItemDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [itemForm, setItemForm] = useState<ItemFormState>(emptyItemForm);
  const [transactionItem, setTransactionItem] = useState<InventoryItem | null>(null);
  const [transactionType, setTransactionType] = useState<InventoryTransactionType>('IN');
  const [transactionQuantity, setTransactionQuantity] = useState('1');
  const [transactionNotes, setTransactionNotes] = useState('');

  const summaryQuery = useQuery({
    queryKey: ['inventory', 'summary'],
    queryFn: async () => requireData(await inventoryApi.listItems({ page: 1, limit: 100 })),
  });
  const itemsQuery = useQuery({
    queryKey: ['inventory', 'items', searchTerm, activeTab],
    queryFn: async () => requireData(await inventoryApi.listItems({
      search: searchTerm.trim() || undefined,
      low_stock: activeTab === 'low-stock' ? true : undefined,
      page: 1,
      limit: 100,
    })),
    enabled: activeTab !== 'alerts',
  });
  const alertsQuery = useQuery({
    queryKey: ['inventory', 'alerts'],
    queryFn: async () => requireData(await inventoryApi.listAlerts({ is_resolved: false, page: 1, limit: 100 })),
  });
  const lowStockQuery = useQuery({
    queryKey: ['inventory', 'low-stock-summary'],
    queryFn: async () => requireData(await inventoryApi.listItems({ low_stock: true, page: 1, limit: 1 })),
  });

  const invalidateInventory = () => {
    void queryClient.invalidateQueries({ queryKey: ['inventory'] });
  };

  const itemMutation = useMutation({
    mutationFn: () => {
      const payload: InventoryItemWrite = {
        name: itemForm.name.trim(),
        sku: itemForm.sku.trim() || undefined,
        category: itemForm.category,
        unit: itemForm.unit,
        current_quantity: Number(itemForm.current_quantity),
        minimum_quantity: Number(itemForm.minimum_quantity),
        reorder_quantity: Number(itemForm.reorder_quantity),
      };
      return editingItem
        ? inventoryApi.updateItem(editingItem.id, payload).then(requireData)
        : inventoryApi.createItem(payload).then(requireData);
    },
    onSuccess: () => {
      toast({ title: editingItem ? 'Inventory item updated' : 'Inventory item created' });
      setItemDialogOpen(false);
      setEditingItem(null);
      setItemForm(emptyItemForm);
      invalidateInventory();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Inventory save failed', description: errorMessage(error) }),
  });

  const transactionMutation = useMutation({
    mutationFn: () => inventoryApi.createTransaction({
      item_id: transactionItem?.id || '',
      transaction_type: transactionType,
      quantity: Number(transactionQuantity),
      notes: transactionNotes.trim() || undefined,
    }).then(requireData),
    onSuccess: () => {
      toast({ title: 'Stock movement recorded' });
      setTransactionItem(null);
      setTransactionNotes('');
      setTransactionQuantity('1');
      setTransactionType('IN');
      invalidateInventory();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Stock movement failed', description: errorMessage(error) }),
  });

  const deleteMutation = useMutation({
    mutationFn: (itemId: string) => inventoryApi.deleteItem(itemId).then(requireData),
    onSuccess: () => {
      toast({ title: 'Inventory item deleted' });
      invalidateInventory();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Inventory delete failed', description: errorMessage(error) }),
  });

  const resolveAlertMutation = useMutation({
    mutationFn: (alertId: string) => inventoryApi.resolveAlert(alertId).then(requireData),
    onSuccess: () => {
      toast({ title: 'Alert resolved' });
      invalidateInventory();
    },
    onError: (error) => toast({ variant: 'destructive', title: 'Alert update failed', description: errorMessage(error) }),
  });

  const summary = summaryQuery.data;
  const displayItems = itemsQuery.data?.items ?? [];
  const alerts = alertsQuery.data?.alerts ?? [];
  const itemNames = new Map((summary?.items ?? []).map((item) => [item.id, item.name]));
  const queryError = summaryQuery.error || itemsQuery.error || alertsQuery.error || lowStockQuery.error;
  const openItemDialog = (item?: InventoryItem) => {
    if (item) {
      setEditingItem(item);
      setItemForm({
        name: item.name,
        sku: item.sku || '',
        category: item.category || 'supplies',
        unit: item.unit || 'each',
        current_quantity: String(item.current_quantity),
        minimum_quantity: String(item.minimum_quantity),
        reorder_quantity: String(item.reorder_quantity),
      });
    } else {
      setEditingItem(null);
      setItemForm(emptyItemForm);
    }
    setItemDialogOpen(true);
  };

  const handleDelete = (item: InventoryItem) => {
    if (window.confirm(`Delete inventory item “${item.name}”? This removes its stock history.`)) {
      deleteMutation.mutate(item.id);
    }
  };

  return (
    <div className="container mx-auto space-y-6 py-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-bold">Inventory Management</h1>
          <p className="text-muted-foreground">Track live supplies, stock movements, and reorder alerts.</p>
        </div>
        {canManageInventory && (
          <Button onClick={() => openItemDialog()}><Plus className="mr-2 h-4 w-4" />Add item</Button>
        )}
      </div>

      {queryError && <Alert variant="destructive"><AlertTitle>Inventory data unavailable</AlertTitle><AlertDescription>{errorMessage(queryError)}</AlertDescription></Alert>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><CardContent className="flex items-center gap-3 p-5"><Package className="h-5 w-5 text-slate-600" /><div><p className="text-sm text-muted-foreground">Total items</p><p className="text-2xl font-bold">{summaryQuery.isLoading ? '…' : summary ? summary.total : '—'}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><ArrowDown className="h-5 w-5 text-red-600" /><div><p className="text-sm text-muted-foreground">Low stock</p><p className="text-2xl font-bold text-red-600">{lowStockQuery.isLoading ? '…' : lowStockQuery.data?.total ?? '—'}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><ArrowUp className="h-5 w-5 text-emerald-600" /><div><p className="text-sm text-muted-foreground">Above minimum</p><p className="text-2xl font-bold text-emerald-600">{summaryQuery.isLoading || lowStockQuery.isLoading ? '…' : summary && lowStockQuery.data ? Math.max(summary.total - lowStockQuery.data.total, 0) : '—'}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-5"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><p className="text-sm text-muted-foreground">Open alerts</p><p className="text-2xl font-bold text-amber-600">{alertsQuery.isLoading ? '…' : alertsQuery.data?.total ?? '—'}</p></div></CardContent></Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList><TabsTrigger value="all">All items</TabsTrigger><TabsTrigger value="low-stock">Low stock</TabsTrigger><TabsTrigger value="alerts">Alerts</TabsTrigger></TabsList>
        <div className="relative max-w-md"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden="true" /><Input className="pl-9" placeholder="Search by name or SKU" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} /></div>

        <TabsContent value="all"><InventoryTable items={displayItems} loading={itemsQuery.isLoading} canManage={canManageInventory} onEdit={openItemDialog} onDelete={handleDelete} onAdjust={setTransactionItem} /></TabsContent>
        <TabsContent value="low-stock"><InventoryTable items={displayItems} loading={itemsQuery.isLoading} canManage={canManageInventory} onEdit={openItemDialog} onDelete={handleDelete} onAdjust={setTransactionItem} /></TabsContent>
        <TabsContent value="alerts">
          <Card><CardHeader><CardTitle>Open inventory alerts</CardTitle></CardHeader><CardContent className="space-y-3">
            {alerts.map((alert) => <div key={alert.id} className="flex flex-col justify-between gap-3 rounded-lg border p-4 sm:flex-row sm:items-center"><div><p className="font-medium">{itemNames.get(alert.item_id) || 'Inventory item'}</p><p className="text-sm text-muted-foreground">{alert.message || displayLabel(alert.alert_type)}</p><p className="text-xs text-muted-foreground">{displayLabel(alert.alert_type)}</p></div>{canManageInventory && <Button size="sm" variant="outline" disabled={resolveAlertMutation.isPending} onClick={() => resolveAlertMutation.mutate(alert.id)}>Resolve</Button>}</div>)}
            {!alertsQuery.isLoading && alerts.length === 0 && <p className="py-8 text-center text-muted-foreground">No open inventory alerts.</p>}
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      <Dialog open={itemDialogOpen} onOpenChange={setItemDialogOpen}><DialogContent><DialogHeader><DialogTitle>{editingItem ? 'Edit inventory item' : 'Add inventory item'}</DialogTitle><DialogDescription>Save the item configuration used by the live stock ledger.</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={(event) => { event.preventDefault(); itemMutation.mutate(); }}><div className="grid gap-4 sm:grid-cols-2"><label className="space-y-1 text-sm font-medium sm:col-span-2">Name<Input required value={itemForm.name} onChange={(event) => setItemForm({ ...itemForm, name: event.target.value })} /></label><label className="space-y-1 text-sm font-medium">SKU<Input value={itemForm.sku} onChange={(event) => setItemForm({ ...itemForm, sku: event.target.value })} /></label><label className="space-y-1 text-sm font-medium">Category<select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={itemForm.category} onChange={(event) => setItemForm({ ...itemForm, category: event.target.value as InventoryCategory })}>{categories.map((category) => <option key={category} value={category}>{displayLabel(category)}</option>)}</select></label><label className="space-y-1 text-sm font-medium">Unit<select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={itemForm.unit} onChange={(event) => setItemForm({ ...itemForm, unit: event.target.value as InventoryUnit })}>{units.map((unit) => <option key={unit} value={unit}>{displayLabel(unit)}</option>)}</select></label><label className="space-y-1 text-sm font-medium">Current quantity<Input required min="0" type="number" value={itemForm.current_quantity} onChange={(event) => setItemForm({ ...itemForm, current_quantity: event.target.value })} /></label><label className="space-y-1 text-sm font-medium">Minimum quantity<Input required min="0" type="number" value={itemForm.minimum_quantity} onChange={(event) => setItemForm({ ...itemForm, minimum_quantity: event.target.value })} /></label><label className="space-y-1 text-sm font-medium">Reorder quantity<Input required min="0" type="number" value={itemForm.reorder_quantity} onChange={(event) => setItemForm({ ...itemForm, reorder_quantity: event.target.value })} /></label></div><DialogFooter><Button type="button" variant="outline" onClick={() => setItemDialogOpen(false)}>Cancel</Button><Button type="submit" disabled={itemMutation.isPending}>{itemMutation.isPending ? 'Saving…' : 'Save item'}</Button></DialogFooter></form></DialogContent></Dialog>

      <Dialog open={transactionItem !== null} onOpenChange={(open) => !open && setTransactionItem(null)}><DialogContent><DialogHeader><DialogTitle>Record stock movement</DialogTitle><DialogDescription>{transactionItem ? `Update ${transactionItem.name}. IN adds stock, OUT removes stock, and ADJUST sets the absolute quantity.` : ''}</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={(event) => { event.preventDefault(); transactionMutation.mutate(); }}><label className="space-y-1 text-sm font-medium">Movement<select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={transactionType} onChange={(event) => setTransactionType(event.target.value as InventoryTransactionType)}><option value="IN">Stock in</option><option value="OUT">Stock out</option><option value="ADJUST">Set quantity</option><option value="RETURN">Return to supplier</option><option value="EXPIRE">Expire/dispose</option></select></label><label className="space-y-1 text-sm font-medium">Quantity<Input required min="0" type="number" value={transactionQuantity} onChange={(event) => setTransactionQuantity(event.target.value)} /></label><label className="space-y-1 text-sm font-medium">Notes<Textarea value={transactionNotes} onChange={(event) => setTransactionNotes(event.target.value)} placeholder="Optional reason or reference" /></label><DialogFooter><Button type="button" variant="outline" onClick={() => setTransactionItem(null)}>Cancel</Button><Button type="submit" disabled={transactionMutation.isPending}>{transactionMutation.isPending ? 'Recording…' : 'Record movement'}</Button></DialogFooter></form></DialogContent></Dialog>
    </div>
  );
}

function InventoryTable({
  items,
  loading,
  canManage,
  onEdit,
  onDelete,
  onAdjust,
}: {
  items: InventoryItem[];
  loading: boolean;
  canManage: boolean;
  onEdit: (item: InventoryItem) => void;
  onDelete: (item: InventoryItem) => void;
  onAdjust: (item: InventoryItem) => void;
}) {
  return <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Item</TableHead><TableHead>SKU</TableHead><TableHead>Category</TableHead><TableHead>Quantity</TableHead><TableHead>Minimum</TableHead><TableHead>Status</TableHead>{canManage && <TableHead className="text-right">Actions</TableHead>}</TableRow></TableHeader><TableBody>{items.map((item) => <TableRow key={item.id}><TableCell><p className="font-medium">{item.name}</p>{item.storage_location && <p className="text-xs text-muted-foreground">{item.storage_location}</p>}</TableCell><TableCell>{item.sku || '—'}</TableCell><TableCell><Badge variant="outline">{item.category ? displayLabel(item.category) : 'Uncategorized'}</Badge></TableCell><TableCell>{item.current_quantity} {item.unit || ''}</TableCell><TableCell>{item.minimum_quantity}</TableCell><TableCell><Badge variant={item.current_quantity <= item.minimum_quantity ? 'destructive' : 'default'}>{item.current_quantity <= item.minimum_quantity ? 'Low stock' : 'In stock'}</Badge></TableCell>{canManage && <TableCell><div className="flex justify-end gap-1"><Button aria-label={`Adjust ${item.name}`} size="icon" variant="ghost" onClick={() => onAdjust(item)}><Boxes className="h-4 w-4" /></Button><Button aria-label={`Edit ${item.name}`} size="icon" variant="ghost" onClick={() => onEdit(item)}><Edit3 className="h-4 w-4" /></Button><Button aria-label={`Delete ${item.name}`} size="icon" variant="ghost" onClick={() => onDelete(item)}><Trash2 className="h-4 w-4 text-destructive" /></Button></div></TableCell>}</TableRow>)}{!loading && items.length === 0 && <TableRow><TableCell colSpan={canManage ? 7 : 6} className="h-24 text-center text-muted-foreground">No inventory items match this search.</TableCell></TableRow>}{loading && <TableRow><TableCell colSpan={canManage ? 7 : 6} className="h-24 text-center text-muted-foreground">Loading inventory…</TableCell></TableRow>}</TableBody></Table></CardContent></Card>;
}
