// ============================================
// CoreDent PMS - Clinic Settings Page
// Admin panel for practice configuration
// ============================================

import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Building2, Clock, Armchair, Calendar } from 'lucide-react';
import { GeneralSettingsTab } from '@/components/settings/GeneralSettingsTab';
import { WorkingHoursTab } from '@/components/settings/WorkingHoursTab';
import { ChairsTab } from '@/components/settings/ChairsTab';
import { AppointmentTypesTab } from '@/components/settings/AppointmentTypesTab';
import type { ClinicSettings } from '@/types/clinic';
import { clinicApi } from '@/services/clinicApi';
import { useToast } from '@/hooks/use-toast';

export default function ClinicSettings() {
  const [settings, setSettings] = useState<ClinicSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    let isActive = true;
    const loadSettings = async () => {
      setIsLoading(true);
      try {
        const response = await clinicApi.getSettings();
        if (!isActive) return;
        if (response.success && response.data) {
          setSettings(response.data);
        } else {
          setSettings(null);
        }
      } catch (error) {
        if (!isActive) return;
        setSettings(null);
        toast({
          title: 'Error',
          description: 'Failed to load clinic settings',
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

  const handleSettingsUpdate = (updates: Partial<ClinicSettings>) => {
    setSettings(prev => (prev ? { ...prev, ...updates } : prev));
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Clinic Settings</h1>
          <p className="text-muted-foreground">Loading clinic settings...</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Clinic Settings</h1>
          <p className="text-muted-foreground">Unable to load clinic settings.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Clinic Settings</h1>
        <p className="text-muted-foreground">
          Configure your practice settings, working hours, and appointment types
        </p>
      </div>

      {/* Settings Tabs */}
      <Tabs defaultValue="general" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="general" className="gap-2">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">General</span>
          </TabsTrigger>
          <TabsTrigger value="hours" className="gap-2">
            <Clock className="h-4 w-4" />
            <span className="hidden sm:inline">Hours</span>
          </TabsTrigger>
          <TabsTrigger value="chairs" className="gap-2">
            <Armchair className="h-4 w-4" />
            <span className="hidden sm:inline">Chairs</span>
          </TabsTrigger>
          <TabsTrigger value="appointments" className="gap-2">
            <Calendar className="h-4 w-4" />
            <span className="hidden sm:inline">Appointments</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <GeneralSettingsTab 
            settings={settings} 
            onUpdate={handleSettingsUpdate} 
          />
        </TabsContent>

        <TabsContent value="hours">
          <WorkingHoursTab 
            workingHours={settings.workingHours} 
            onUpdate={(workingHours) => handleSettingsUpdate({ workingHours })} 
          />
        </TabsContent>

        <TabsContent value="chairs">
          <ChairsTab 
            chairs={settings.chairs} 
            onUpdate={(chairs) => handleSettingsUpdate({ chairs })} 
          />
        </TabsContent>

        <TabsContent value="appointments">
          <AppointmentTypesTab 
            appointmentTypes={settings.appointmentTypes} 
            onUpdate={(appointmentTypes) => handleSettingsUpdate({ appointmentTypes })} 
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
