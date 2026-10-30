import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Edit, Plus, Search } from 'lucide-react';
import { insuranceApi } from '@/services/insuranceApi';
import type { InsuranceCarrier } from '@/types/insurance';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface InsuranceListProps {
  onEdit?: (carrier: InsuranceCarrier) => void;
  onCreate?: () => void;
}

export function InsuranceList({ onEdit, onCreate }: InsuranceListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const { data: carriers, isLoading, error } = useQuery({
    queryKey: ['insurance-carriers'],
    queryFn: () => insuranceApi.getCarriers(),
  });

  const normalizedSearch = searchTerm.toLowerCase();
  const filteredCarriers = carriers?.filter(carrier =>
    carrier.name.toLowerCase().includes(normalizedSearch) ||
    carrier.email?.toLowerCase().includes(normalizedSearch) ||
    carrier.phone?.toLowerCase().includes(normalizedSearch) ||
    carrier.payerId?.toLowerCase().includes(normalizedSearch),
  ) ?? [];

  if (isLoading) {
    return <div className="flex items-center justify-center py-8"><div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary" /></div>;
  }

  if (error) {
    return <div className="py-8 text-center text-red-500">Failed to load insurance carriers</div>;
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row">
        <div className="flex-1">
          <CardTitle>Insurance Carriers</CardTitle>
          <p className="text-sm text-muted-foreground">Manage insurance carriers and their details</p>
        </div>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search carriers..." value={searchTerm} onChange={event => setSearchTerm(event.target.value)} className="pl-10" />
          </div>
          <Button onClick={() => onCreate?.()}><Plus className="mr-2 h-4 w-4" />Add Carrier</Button>
        </div>
      </CardHeader>
      <CardContent>
        {filteredCarriers.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">{searchTerm ? 'No carriers found matching your search' : 'No insurance carriers yet'}</div>
        ) : (
          <div className="space-y-4">
            {filteredCarriers.map(carrier => (
              <div key={carrier.id} className="flex flex-col gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50 sm:flex-row">
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold">{carrier.name}</h3>
                    {carrier.isActive && <Badge className="bg-green-500">Active</Badge>}
                  </div>
                  <div className="grid grid-cols-1 gap-4 text-sm text-muted-foreground md:grid-cols-3">
                    {carrier.phone && <div><span className="font-medium">Phone:</span><span className="ml-2">{carrier.phone}</span></div>}
                    {carrier.email && <div><span className="font-medium">Email:</span><span className="ml-2">{carrier.email}</span></div>}
                    {carrier.payerId && <div><span className="font-medium">Payer ID:</span><span className="ml-2">{carrier.payerId}</span></div>}
                  </div>
                  {carrier.addressLine1 && (
                    <p className="text-sm text-muted-foreground">
                      <span className="font-medium">Address:</span> {carrier.addressLine1}
                      {carrier.addressLine2 && `, ${carrier.addressLine2}`}
                      {carrier.city && `, ${carrier.city}`}
                      {carrier.state && `, ${carrier.state}`}
                      {carrier.zipCode && ` ${carrier.zipCode}`}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => onEdit?.(carrier)}><Edit className="mr-2 h-4 w-4" />Edit</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
