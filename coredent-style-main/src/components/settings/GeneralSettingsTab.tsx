import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { clinicApi } from '@/services/clinicApi';
import type { ClinicSettings } from '@/types/clinic';
import { US_STATES } from '@/types/clinic';
import {
  RETENTION_PRESET_OPTIONS,
  getRetentionPreset,
  PLATFORM_RETENTION_FLOOR_YEARS,
} from '@/lib/retentionPresets';
import { Loader2, Save } from 'lucide-react';

interface GeneralSettingsTabProps {
  settings: ClinicSettings;
  onUpdate: (updates: Partial<ClinicSettings>) => void;
}

export function GeneralSettingsTab({ settings, onUpdate }: GeneralSettingsTabProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: settings.name || '',
    email: settings.email || '',
    phone: settings.phone || '',
    website: settings.website || '',
    fax: settings.fax || '',
    street: settings.address?.street || '',
    suite: settings.address?.suite || '',
    city: settings.address?.city || '',
    state: settings.address?.state || '',
    zipCode: settings.address?.zipCode || '',
    country: settings.address?.country || 'USA',
    timezone: settings.timezone || 'America/New_York',
    currency: settings.currency || 'USD',
    dateFormat: settings.dateFormat || 'MM/DD/YYYY',
    retentionYears: settings.retentionYears ?? null,
    jurisdiction: settings.jurisdiction || '',
    majorityAge: settings.majorityAge ?? 18,
    minorRetentionYears: settings.minorRetentionYears ?? 7,
  });

  // The guidance preset matching the stored jurisdiction (fallback = US default).
  const activePreset = getRetentionPreset(
    formData.jurisdiction === '' ? null : formData.jurisdiction
  );

  const handleJurisdictionChange = (code: string) => {
    const preset = getRetentionPreset(code);
    setFormData({
      ...formData,
      jurisdiction: code,
      // Auto-fill all suggested values; never lower an already-higher adult
      // value on a mere jurisdiction switch (the practice can adjust upward).
      retentionYears:
        formData.retentionYears != null && formData.retentionYears > preset.adultYears
          ? formData.retentionYears
          : preset.adultYears,
      majorityAge: preset.majorityAge,
      minorRetentionYears: preset.minorRetentionYears,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const updates: Partial<ClinicSettings> = {
        name: formData.name,
        email: formData.email,
        phone: formData.phone,
        website: formData.website,
        fax: formData.fax,
        timezone: formData.timezone,
        currency: formData.currency,
        dateFormat: formData.dateFormat as any,
        retentionYears: formData.retentionYears,
        jurisdiction: formData.jurisdiction || null,
        majorityAge: formData.majorityAge,
        minorRetentionYears: formData.minorRetentionYears,
        address: {
          street: formData.street,
          suite: formData.suite,
          city: formData.city,
          state: formData.state,
          zipCode: formData.zipCode,
          country: formData.country,
        },
      };

      const res = await clinicApi.updateSettings(updates);
      if (res.success) {
        onUpdate(updates);
        toast({
          title: 'Settings Saved',
          description: 'General clinic settings have been updated.',
        });
      } else {
        toast({
          title: 'Error',
          description: res.error?.message || 'Failed to save settings',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'An unexpected error occurred while saving.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-none shadow-[0_15px_40px_rgba(0,0,0,0.02)] rounded-3xl overflow-hidden bg-white">
      <CardHeader>
        <CardTitle className="text-xl font-black text-slate-800 tracking-tight">Clinic Profile & Info</CardTitle>
        <CardDescription className="text-slate-400 font-medium">Update the primary contact, location details, and regional settings for your clinic.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Clinic Name</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="h-12 rounded-xl border-slate-200 font-bold"
                required
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Primary Email</Label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="h-12 rounded-xl border-slate-200 font-medium"
                required
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Phone Number</Label>
              <Input
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="h-12 rounded-xl border-slate-200 font-medium"
                required
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Website URL</Label>
              <Input
                value={formData.website}
                onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                className="h-12 rounded-xl border-slate-200 font-medium"
              />
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h4 className="text-sm font-black text-slate-800 tracking-tight uppercase tracking-widest text-slate-400 text-[10px]">Location Address</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2 md:col-span-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Street Address</Label>
                <Input
                  value={formData.street}
                  onChange={(e) => setFormData({ ...formData, street: e.target.value })}
                  className="h-12 rounded-xl border-slate-200 font-medium"
                  required
                />
              </div>
              <div className="grid grid-cols-3 md:col-span-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400">City</Label>
                  <Input
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="h-12 rounded-xl border-slate-200 font-medium"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400">State</Label>
                  <Select
                    value={formData.state}
                    onValueChange={(val) => setFormData({ ...formData, state: val })}
                  >
                    <SelectTrigger className="h-12 rounded-xl border-slate-200 font-bold">
                      <SelectValue placeholder="State" />
                    </SelectTrigger>
                    <SelectContent>
                      {US_STATES.map((st) => (
                        <SelectItem key={st.code} value={st.code}>
                          {st.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs font-black uppercase tracking-widest text-slate-400">ZIP Code</Label>
                  <Input
                    value={formData.zipCode}
                    onChange={(e) => setFormData({ ...formData, zipCode: e.target.value })}
                    className="h-12 rounded-xl border-slate-200 font-medium"
                    required
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h4 className="text-sm font-black text-slate-800 tracking-tight uppercase tracking-widest text-slate-400 text-[10px]">Localization Settings</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Timezone</Label>
                <Select value={formData.timezone} onValueChange={(val) => setFormData({ ...formData, timezone: val })}>
                  <SelectTrigger className="h-12 rounded-xl border-slate-200 font-medium">
                    <SelectValue placeholder="Select timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="America/New_York">Eastern Time (ET)</SelectItem>
                    <SelectItem value="America/Chicago">Central Time (CT)</SelectItem>
                    <SelectItem value="America/Denver">Mountain Time (MT)</SelectItem>
                    <SelectItem value="America/Los_Angeles">Pacific Time (PT)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Currency</Label>
                <Select value={formData.currency} onValueChange={(val) => setFormData({ ...formData, currency: val })}>
                  <SelectTrigger className="h-12 rounded-xl border-slate-200 font-bold">
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD ($)</SelectItem>
                    <SelectItem value="EUR">EUR (€)</SelectItem>
                    <SelectItem value="INR">INR (₹)</SelectItem>
                    <SelectItem value="GBP">GBP (£)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Date Format</Label>
                <Select value={formData.dateFormat} onValueChange={(val) => setFormData({ ...formData, dateFormat: val as 'MM/DD/YYYY' | 'DD/MM/YYYY' | 'YYYY-MM-DD' })}>
                  <SelectTrigger className="h-12 rounded-xl border-slate-200 font-medium">
                    <SelectValue placeholder="Select date format" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="MM/DD/YYYY">MM/DD/YYYY</SelectItem>
                    <SelectItem value="DD/MM/YYYY">DD/MM/YYYY</SelectItem>
                    <SelectItem value="YYYY-MM-DD">YYYY-MM-DD</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Record Retention (years)</Label>
                <Input
                  type="number"
                  min="7"
                  max="100"
                  value={formData.retentionYears ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      retentionYears: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                  placeholder="7 (platform default)"
                  className="h-12 rounded-xl border-slate-200 font-medium"
                />
                <p className="text-[11px] text-slate-400 leading-snug">
                  How long anonymized patient records are kept before the scheduled purge.
                  Values below the platform floor (7 yrs) are ignored; this can only extend, never shorten.
                </p>
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label className="text-xs font-black uppercase tracking-widest text-slate-400">Jurisdiction (retention guidance)</Label>
                <Select value={formData.jurisdiction} onValueChange={handleJurisdictionChange}>
                  <SelectTrigger className="h-12 rounded-xl border-slate-200 font-medium">
                    <SelectValue placeholder="Select jurisdiction for guidance..." />
                  </SelectTrigger>
                  <SelectContent className="max-h-80">
                    {RETENTION_PRESET_OPTIONS.map((group) => (
                      <React.Fragment key={group.group}>
                        <div className="px-2 py-1.5 text-[11px] font-bold uppercase tracking-widest text-slate-400">
                          {group.group}
                        </div>
                        {group.items.map((item) => (
                          <SelectItem key={item.code} value={item.code}>
                            {item.label} — suggested {item.adultYears}y
                          </SelectItem>
                        ))}
                      </React.Fragment>
                    ))}
                  </SelectContent>
                </Select>
                {formData.jurisdiction !== '' && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-500 leading-snug space-y-1">
                    <p>
                      <span className="font-bold">Suggested: {activePreset.adultYears} years.</span>{' '}
                      {activePreset.adultYears !== formData.retentionYears && (
                        <button
                          type="button"
                          className="text-blue-600 underline"
                          onClick={() =>
                            setFormData({ ...formData, retentionYears: activePreset.adultYears })
                          }
                        >
                          Apply suggestion
                        </button>
                      )}
                    </p>
                    <p>Minors: {activePreset.minorRule}</p>
                    {activePreset.note && <p className="italic">{activePreset.note}</p>}
                    <div className="grid md:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Age of majority</Label>
                        <Input
                          type="number"
                          min="14"
                          max="21"
                          value={formData.majorityAge}
                          onChange={(e) => setFormData({ ...formData, majorityAge: Number(e.target.value) })}
                          className="h-10 rounded-xl border-slate-200 font-medium"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Minor extra years</Label>
                        <Input
                          type="number"
                          min="0"
                          max="40"
                          value={formData.minorRetentionYears}
                          onChange={(e) => setFormData({ ...formData, minorRetentionYears: Number(e.target.value) })}
                          className="h-10 rounded-xl border-slate-200 font-medium"
                        />
                      </div>
                    </div>
                    <p>
                      Effective purge window is the maximum of the platform floor (
                      {PLATFORM_RETENTION_FLOOR_YEARS}y) and this value. Guidance only — verify
                      against your state board / counsel before relying on it.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <Button
              type="submit"
              disabled={isSaving}
              className="px-8 h-12 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-black flex items-center justify-center gap-2 shadow-lg shadow-blue-100"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" /> Save Changes
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
