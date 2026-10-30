// ============================================
// CoreDent PMS - Settings Page
// Unified settings management for admins
// ============================================

import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Building2, Users, Calendar, CreditCard, Zap } from 'lucide-react';
import { GeneralSettingsTab } from '@/components/settings/GeneralSettingsTab';
import { WorkingHoursTab } from '@/components/settings/WorkingHoursTab';
import { ChairsTab } from '@/components/settings/ChairsTab';
import { AppointmentTypesTab } from '@/components/settings/AppointmentTypesTab';
import { BillingPreferencesTab } from '@/components/settings/BillingPreferencesTab';
import { StaffSettingsTab } from '@/components/settings/StaffSettingsTab';
import { AutomationsTab } from '@/components/settings/AutomationsTab';
import type { ClinicSettings } from '@/types/clinic';
import type { BillingPreferences } from '@/types/settings';
import { clinicApi } from '@/services/clinicApi';
import { settingsApi } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

export default function Settings() {
  const [clinicSettings, setClinicSettings] = useState<ClinicSettings | null>(null);
  const [billingPreferences, setBillingPreferences] = useState<BillingPreferences | null>(null);
  const [activeTab, setActiveTab] = useState('clinic');
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  // effect:audited — Load settings data on mount with cleanup
  useEffect(() => {
    let isActive = true;
    const loadSettings = async () => {
      setIsLoading(true);
      try {
        const [clinicResponse, billingResponse] = await Promise.all([
          clinicApi.getSettings(),
          settingsApi.getBillingPreferences(),
        ]);
        if (!isActive) return;
        if (clinicResponse.success && clinicResponse.data) {
          setClinicSettings(clinicResponse.data);
        } else {
          setClinicSettings(null);
        }
        if (billingResponse.success && billingResponse.data) {
          setBillingPreferences(billingResponse.data);
        } else {
          setBillingPreferences(null);
        }
      } catch (error) {
        if (!isActive) return;
        setClinicSettings(null);
        setBillingPreferences(null);
        toast({
          title: 'Error',
          description: 'Failed to load settings',
          variant: 'destructive',
        });
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadSettings();

    return () => {
      isActive = false;
    };
  }, [toast]);

  const handleClinicUpdate = (updates: Partial<ClinicSettings>) => {
    setClinicSettings(prev => (prev ? { ...prev, ...updates } : prev));
  };

  const handleBillingUpdate = (preferences: BillingPreferences) => {
    setBillingPreferences(preferences);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Loading settings...</p>
        </div>
      </div>
    );
  }

  if (!clinicSettings || !billingPreferences) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Unable to load settings.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your practice settings, staff, and billing preferences
        </p>
      </div>

      {/* Settings Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 lg:w-auto lg:inline-grid lg:grid-cols-5">
          <TabsTrigger value="clinic" className="gap-2">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">Clinic</span>
          </TabsTrigger>
          <TabsTrigger value="staff" className="gap-2">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">Staff</span>
          </TabsTrigger>
          <TabsTrigger value="appointments" className="gap-2">
            <Calendar className="h-4 w-4" />
            <span className="hidden sm:inline">Appointments</span>
          </TabsTrigger>
          <TabsTrigger value="billing" className="gap-2">
            <CreditCard className="h-4 w-4" />
            <span className="hidden sm:inline">Billing</span>
          </TabsTrigger>
          <TabsTrigger value="automations" className="gap-2">
            <Zap className="h-4 w-4" />
            <span className="hidden sm:inline">Automations</span>
          </TabsTrigger>
        </TabsList>

        {/* Clinic Settings */}
        <TabsContent value="clinic" className="space-y-6">
          <Tabs defaultValue="general" className="space-y-4">
            <TabsList>
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="hours">Working Hours</TabsTrigger>
              <TabsTrigger value="chairs">Chairs</TabsTrigger>
            </TabsList>

            <TabsContent value="general">
              <GeneralSettingsTab 
                settings={clinicSettings} 
                onUpdate={handleClinicUpdate} 
              />
            </TabsContent>

            <TabsContent value="hours">
              <WorkingHoursTab 
                workingHours={clinicSettings.workingHours} 
                onUpdate={(workingHours) => handleClinicUpdate({ workingHours })} 
              />
            </TabsContent>

            <TabsContent value="chairs">
              <ChairsTab 
                chairs={clinicSettings.chairs} 
                onUpdate={(chairs) => handleClinicUpdate({ chairs })} 
              />
            </TabsContent>
          </Tabs>
        </TabsContent>

        {/* Staff Management */}
        <TabsContent value="staff">
          <StaffSettingsTab />
        </TabsContent>

        {/* Appointment Types */}
        <TabsContent value="appointments">
          <AppointmentTypesTab 
            appointmentTypes={clinicSettings.appointmentTypes} 
            onUpdate={(appointmentTypes) => handleClinicUpdate({ appointmentTypes })} 
          />
        </TabsContent>

        {/* Billing Preferences */}
        <TabsContent value="billing">
          <BillingPreferencesTab 
            preferences={billingPreferences}
            onUpdate={handleBillingUpdate}
          />
        </TabsContent>

        {/* Automations */}
        <TabsContent value="automations">
          <AutomationsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
