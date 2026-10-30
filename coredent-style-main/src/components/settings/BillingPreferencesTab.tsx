import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';
import { settingsApi } from '@/services/api';
import {
  paymentMethodLabels,
  type BillingPreferences,
  type PaymentMethod,
} from '@/types/settings';
import { Loader2, Save } from 'lucide-react';

interface BillingPreferencesTabProps {
  preferences: BillingPreferences;
  onUpdate: (preferences: BillingPreferences) => void;
}

const paymentMethods = Object.keys(paymentMethodLabels) as PaymentMethod[];

export function BillingPreferencesTab({ preferences, onUpdate }: BillingPreferencesTabProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState<BillingPreferences>({ ...preferences });

  const togglePaymentMethod = (method: PaymentMethod, enabled: boolean) => {
    setFormData(current => ({
      ...current,
      acceptedPaymentMethods: enabled
        ? Array.from(new Set([...current.acceptedPaymentMethods, method]))
        : current.acceptedPaymentMethods.filter(item => item !== method),
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (formData.acceptedPaymentMethods.length === 0) {
      toast({
        title: 'Payment method required',
        description: 'Select at least one accepted payment method.',
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      const response = await settingsApi.updateBillingPreferences(formData);
      if (response.success && response.data) {
        onUpdate(response.data);
        toast({
          title: 'Preferences saved',
          description: 'Persisted billing preferences were updated.',
        });
      } else {
        toast({
          title: 'Error',
          description: response.error?.message || 'Failed to update billing preferences',
          variant: 'destructive',
        });
      }
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to update preferences due to a network issue.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
      <CardHeader>
        <CardTitle className="text-xl font-black text-slate-800 tracking-tight">
          Billing & Invoicing Preferences
        </CardTitle>
        <CardDescription className="text-slate-400 font-medium">
          Configure persisted invoice defaults, accepted payment methods, and reminders.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <Label htmlFor="invoice-prefix">Invoice Prefix</Label>
              <Input
                id="invoice-prefix"
                value={formData.invoicePrefix}
                onChange={event => setFormData({ ...formData, invoicePrefix: event.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payment-terms">Default Terms (Days)</Label>
              <Input
                id="payment-terms"
                type="number"
                min="0"
                value={formData.paymentTerms}
                onChange={event => setFormData({ ...formData, paymentTerms: Number(event.target.value) })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="billing-currency">Currency</Label>
              <Input
                id="billing-currency"
                value={formData.currency}
                onChange={event => setFormData({ ...formData, currency: event.target.value.toUpperCase() })}
                maxLength={3}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t pt-6">
            <div className="space-y-2">
              <Label htmlFor="tax-rate">Tax Rate (%)</Label>
              <Input
                id="tax-rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formData.taxRate}
                onChange={event => setFormData({ ...formData, taxRate: Number(event.target.value) })}
                required
              />
              <p className="text-xs text-muted-foreground">Use 0 when invoices are not taxed.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="late-rate">Late Fee (%)</Label>
              <Input
                id="late-rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formData.lateFeePercentage}
                onChange={event => setFormData({ ...formData, lateFeePercentage: Number(event.target.value) })}
                required
              />
              <p className="text-xs text-muted-foreground">Use 0 to disable overdue late fees.</p>
            </div>
          </div>

          <fieldset className="space-y-3 border-t pt-6">
            <legend className="text-sm font-semibold">Accepted Payment Methods</legend>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {paymentMethods.map(method => (
                <label key={method} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={formData.acceptedPaymentMethods.includes(method)}
                    onCheckedChange={checked => togglePaymentMethod(method, checked === true)}
                  />
                  {paymentMethodLabels[method]}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t pt-6">
            <div className="flex justify-between items-center p-4 border rounded-2xl">
              <div>
                <Label>Auto-Send Invoices</Label>
                <p className="text-xs text-muted-foreground">Queue pending invoices for patient email delivery.</p>
              </div>
              <Switch
                checked={formData.autoSendInvoices}
                onCheckedChange={checked => setFormData({ ...formData, autoSendInvoices: checked })}
              />
            </div>
            <div className="space-y-3 p-4 border rounded-2xl">
              <div className="flex justify-between items-center">
                <div>
                  <Label>Auto-Send Reminders</Label>
                  <p className="text-xs text-muted-foreground">Schedule invoice payment reminders.</p>
                </div>
                <Switch
                  checked={formData.autoSendReminders}
                  onCheckedChange={checked => setFormData({ ...formData, autoSendReminders: checked })}
                />
              </div>
              {formData.autoSendReminders && (
                <div className="space-y-2">
                  <Label htmlFor="reminder-days">Days Before Due Date</Label>
                  <Input
                    id="reminder-days"
                    type="number"
                    min="0"
                    value={formData.reminderDaysBefore}
                    onChange={event => setFormData({ ...formData, reminderDaysBefore: Number(event.target.value) })}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
              {isSaving ? 'Saving...' : 'Save Preferences'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
