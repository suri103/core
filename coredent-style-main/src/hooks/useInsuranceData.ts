import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import { insuranceApi } from '@/services/insuranceApi';
import type { InsuranceCarrier, InsuranceClaim, InsurancePreAuthorization } from '@/types/insurance';

export function useInsuranceData() {
  const [carriers, setCarriers] = useState<InsuranceCarrier[]>([]);
  const [claims, setClaims] = useState<InsuranceClaim[]>([]);
  const [preAuths, setPreAuths] = useState<InsurancePreAuthorization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [carriersData, claimsPage, preAuthPage] = await Promise.all([
        insuranceApi.getCarriers(),
        insuranceApi.getClaims(),
        insuranceApi.getPreAuthorizations(),
      ]);
      setCarriers(carriersData);
      setClaims(claimsPage.items);
      setPreAuths(preAuthPage.items);
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to load insurance data',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const refetch = useCallback(async () => {
    await loadData();
  }, [loadData]);

  return { carriers, claims, preAuths, isLoading, refetch };
}
