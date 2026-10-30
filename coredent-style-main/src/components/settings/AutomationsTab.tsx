import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { automationApi } from '@/services/automationApi';
import type { AutomationWebhook, AutomationEvent } from '@/types/automation';
import { Loader2, Plus, Zap, Settings2, Trash2, Activity } from 'lucide-react';

const EVENT_LABELS: Record<AutomationEvent, string> = {
  appointment_booked: 'Appointment Booked',
  appointment_cancelled: 'Appointment Canceled',
  appointment_completed: 'Appointment Completed',
  appointment_confirmed: 'Appointment Confirmed',
  appointment_no_show: 'Appointment No-Show',
  patient_created: 'New Patient Registered',
  patient_registered: 'Patient Registered',
  invoice_created: 'Invoice Created',
  invoice_overdue: 'Invoice Overdue Warning',
  payment_received: 'Payment Received',
  payment_refunded: 'Payment Refunded',
  review_request: 'Review Request',
  treatment_plan_approved: 'Treatment Plan Approved',
  treatment_plan_created: 'Treatment Plan Formulated',
};

export function AutomationsTab() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState<string | null>(null);
  const [webhooks, setWebhooks] = useState<AutomationWebhook[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [event, setEvent] = useState<AutomationEvent>('appointment_booked');
  const [secretToken, setSecretToken] = useState('');

  const loadWebhooks = async () => {
    setLoading(true);
    try {
      const data = await automationApi.getWebhooks();
      setWebhooks(data);
    } catch (err) {
      console.error('Failed to load webhooks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWebhooks();
  }, []);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        name,
        url,
        event,
        secretToken: secretToken.trim() || undefined,
        isActive: true,
      };
      const res = await automationApi.createWebhook(payload);
      setWebhooks((prev) => [...prev, res]);
      toast({
        title: 'Webhook Registered',
        description: `Automated trigger "${name}" registered successfully.`,
      });
      setIsOpen(false);
      // Clear
      setName('');
      setUrl('');
      setSecretToken('');
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to register webhook',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggle = async (id: string) => {
    try {
      const res = await automationApi.toggleWebhook(id);
      setWebhooks((prev) => prev.map((w) => (w.id === id ? res : w)));
      toast({
        title: 'Status Toggled',
        description: `Automation "${res.name}" is now ${res.isActive ? 'active' : 'inactive'}.`,
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to toggle status.',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await automationApi.deleteWebhook(id);
      setWebhooks((prev) => prev.filter((w) => w.id !== id));
      toast({
        title: 'Automation Removed',
        description: 'Webhook triggers deleted successfully.',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete webhook.',
        variant: 'destructive',
      });
    }
  };

  const handleTestConnection = async (webhook: AutomationWebhook) => {
    setIsTesting(webhook.id);
    try {
      const success = await automationApi.testWebhook(webhook.url, webhook.secretToken);
      if (success) {
        toast({
          title: 'Connection Successful',
          description: 'Webhook successfully responded to ping payload (200 OK).',
        });
      } else {
        toast({
          title: 'Connection Failed',
          description: 'Failed to ping webhook URL. Please check the endpoint or CORS settings.',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Network failure during test dispatch.',
        variant: 'destructive',
      });
    } finally {
      setIsTesting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
        <CardHeader className="flex flex-row justify-between items-center pb-4">
          <div>
            <CardTitle className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              <Zap className="w-5 h-5 text-indigo-600 fill-indigo-100" /> Webhook Automations (n8n / Zapier)
            </CardTitle>
            <CardDescription className="text-slate-400 font-medium">Trigger third-party automated workflows (SMS, email outreach, custom analytics) upon clinical events.</CardDescription>
          </div>
          <Button onClick={() => setIsOpen(true)} className="h-10 rounded-xl font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 shadow-md shadow-blue-100">
            <Plus className="w-4 h-4" /> Add Webhook
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {webhooks.length === 0 ? (
              <div className="text-center py-12 text-slate-400 space-y-3 bg-slate-50/50 rounded-2xl border border-dashed border-slate-100">
                <Settings2 className="w-8 h-8 mx-auto text-slate-300" />
                <p className="font-bold text-sm">No webhooks configured</p>
                <p className="text-xs max-w-xs mx-auto text-slate-400">Connect to n8n, Make, or Zapier webhooks to build powerful messaging campaigns.</p>
              </div>
            ) : (
              webhooks.map((w) => (
                <div key={w.id} className="p-5 border border-slate-100 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white hover:border-indigo-200 transition-colors">
                  <div className="space-y-1.5 max-w-md">
                    <div className="flex items-center gap-2">
                      <h4 className="font-black text-slate-800 text-sm">{w.name}</h4>
                      <Badge variant="outline" className="font-bold uppercase tracking-wider text-[8px] bg-indigo-50 text-indigo-600 border-none">
                        {EVENT_LABELS[w.event]}
                      </Badge>
                    </div>
                    <p className="text-[10px] text-slate-400 font-mono break-all leading-relaxed">{w.url}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={isTesting === w.id}
                      onClick={() => handleTestConnection(w)}
                      className="h-8 rounded-lg font-bold text-xs text-indigo-600 hover:bg-indigo-50"
                    >
                      {isTesting === w.id ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> Ping...
                        </>
                      ) : (
                        <>
                          <Activity className="w-3.5 h-3.5 mr-1" /> Test Link
                        </>
                      )}
                    </Button>

                    <div className="flex items-center gap-2">
                      <Switch
                        checked={w.isActive}
                        onCheckedChange={() => handleToggle(w.id)}
                      />
                      <span className="text-[10px] font-black uppercase text-slate-400 w-10">
                        {w.isActive ? 'Active' : 'Muted'}
                      </span>
                    </div>

                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(w.id)}
                      className="h-8 w-8 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Webhook Form Dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-[420px] rounded-3xl p-8">
          <DialogHeader>
            <DialogTitle className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-1.5">
              <Zap className="w-5 h-5 text-blue-500" /> New Webhook Trigger
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400 font-medium mt-0.5">
              Hook into clinical updates and call third-party endpoints.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateSubmit} className="space-y-4 py-3">
            <div className="space-y-2">
              <Label htmlFor="webhook-name" className="text-xs font-black uppercase tracking-widest text-slate-400">Trigger Name</Label>
              <Input
                id="webhook-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. n8n SMS Campaign Manager"
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-url" className="text-xs font-black uppercase tracking-widest text-slate-400">Endpoint Webhook URL</Label>
              <Input
                id="webhook-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://primary.n8n.cloud/webhook/..."
                className="h-12 rounded-xl border-slate-200 font-medium"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-event" className="text-xs font-black uppercase tracking-widest text-slate-400">Trigger Event</Label>
              <Select value={event} onValueChange={(val: any) => setEvent(val)}>
                <SelectTrigger id="webhook-event" className="h-12 rounded-xl border-slate-200 font-bold">
                  <SelectValue placeholder="Choose event trigger" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="appointment_booked">Appointment Booked</SelectItem>
                  <SelectItem value="appointment_cancelled">Appointment Canceled</SelectItem>
                  <SelectItem value="patient_created">New Patient Registered</SelectItem>
                  <SelectItem value="invoice_created">Invoice Created</SelectItem>
                  <SelectItem value="invoice_overdue">Invoice Overdue Warning</SelectItem>
                  <SelectItem value="payment_received">Payment Received</SelectItem>
                  <SelectItem value="payment_refunded">Payment Refunded</SelectItem>
                  <SelectItem value="treatment_plan_created">Treatment Plan Formulated</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-token" className="text-xs font-black uppercase tracking-widest text-slate-400">Security Secret Token (Optional)</Label>
              <Input
                id="webhook-token"
                value={secretToken}
                onChange={(e) => setSecretToken(e.target.value)}
                placeholder="Authorization header token"
                className="h-12 rounded-xl border-slate-200 font-medium"
              />
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4">
              <Button type="button" variant="outline" onClick={() => setIsOpen(false)} className="rounded-xl font-bold h-12 border-slate-200">
                Cancel
              </Button>
              <Button type="submit" disabled={isSaving} className="rounded-xl font-black bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-100 h-12 flex items-center justify-center gap-2">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Register Webhook'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
