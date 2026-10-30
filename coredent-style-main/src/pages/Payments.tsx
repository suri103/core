/**
 * Payments Page
 * Credit card processing, recurring billing, payment terminals
 * Supports: Stripe (US) and Razorpay (India - UPI/Paytm/PhonePe)
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  Table,
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Search, 
  Plus, 
  CreditCard, 
  DollarSign, 
  TrendingUp,
  Clock,
  RefreshCw,
  Terminal,
  Settings,
  Smartphone,
  Loader2
} from "lucide-react";
import {
  usePaymentStats,
  useTransactions,
  useRecurringPlans,
  useTerminals,
} from "@/hooks/usePayments";
import { useCurrencyFormatter } from "@/hooks/useCurrencyFormatter";

export default function Payments() {
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreditCardDialog, setShowCreditCardDialog] = useState(false);

  // Fetch data from API using React Query hooks
  const { data: statsData, isLoading: statsLoading, isError: statsError } = usePaymentStats();
  const { data: transactionsData, isLoading: transactionsLoading, isError: transactionsError } = useTransactions({ search: searchTerm || undefined });
  const { data: recurringData, isLoading: recurringLoading, isError: recurringError } = useRecurringPlans();
  const { data: terminalsData, isLoading: terminalsLoading, isError: terminalsError } = useTerminals();
  const hasPaymentDataError = statsError || transactionsError || recurringError || terminalsError;

  const stats = statsData?.data;
  const transactions = transactionsData?.data?.transactions ?? [];
  const recurringPlans = recurringData?.data?.plans ?? [];
  const terminals = terminalsData?.data?.terminals ?? [];

  const { formatCurrency: formatUSD } = useCurrencyFormatter();

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Payments</h1>
          <p className="text-muted-foreground">Credit card processing and billing</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Terminal className="mr-2 h-4 w-4" />
            Terminals
          </Button>
          <Button disabled title="UPI payments require a server-side Razorpay order endpoint">
            <Smartphone className="mr-2 h-4 w-4" />
            UPI unavailable
          </Button>
          <Button onClick={() => setShowCreditCardDialog(true)}>
            <CreditCard className="mr-2 h-4 w-4" />
            Process Payment
          </Button>
        </div>
      </div>

      {hasPaymentDataError && (
        <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          Payment data is currently unavailable. No estimated or demo financial data is shown. Retry after the payment service is restored.
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Today's Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-green-500">
                  {formatUSD(stats?.todayRevenue ?? 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats?.todayTransactions ?? 0} transactions
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">This Month</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {formatUSD(stats?.monthRevenue ?? 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats?.monthGrowth ? `+${stats.monthGrowth}% from last month` : 'No data'}
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Payments</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-yellow-500">
                  {formatUSD(stats?.pendingPayments ?? 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats?.pendingCount ?? 0} pending
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recurring Revenue</CardTitle>
            <RefreshCw className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-blue-500">
                  {formatUSD(stats?.recurringRevenue ?? 0)}
                </div>
                <p className="text-xs text-muted-foreground">monthly recurring</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="transactions" className="space-y-4">
        <TabsList>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="recurring">Recurring Billing</TabsTrigger>
          <TabsTrigger value="terminals">Terminals</TabsTrigger>
          <TabsTrigger value="settings">Payment Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="transactions">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Recent Transactions</CardTitle>
                <div className="relative w-64">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input 
                    placeholder="Search transactions..." 
                    className="pl-10"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {transactionsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : transactions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No transactions found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Patient</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Payment Method</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((txn) => (
                      <TableRow key={txn.id}>
                        <TableCell className="font-medium">{txn.patient}</TableCell>
                        <TableCell>{formatUSD(txn.amount)}</TableCell>
                        <TableCell><Badge variant="outline">{txn.type}</Badge></TableCell>
                        <TableCell className="text-muted-foreground">{txn.method}</TableCell>
                        <TableCell>
                          <Badge className={txn.status === 'Completed' ? 'bg-green-500' : txn.status === 'Failed' ? 'bg-red-500' : 'bg-yellow-500'}>
                            {txn.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{txn.date}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recurring">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Recurring Billing Plans</CardTitle>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  New Plan
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {recurringLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : recurringPlans.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No recurring billing plans found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Patient</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Frequency</TableHead>
                      <TableHead>Next Date</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recurringPlans.map((plan) => (
                      <TableRow key={plan.id}>
                        <TableCell className="font-medium">{plan.patient}</TableCell>
                        <TableCell>{plan.plan}</TableCell>
                        <TableCell>{formatUSD(plan.amount)}</TableCell>
                        <TableCell><Badge variant="outline">{plan.frequency}</Badge></TableCell>
                        <TableCell>{plan.nextDate}</TableCell>
                        <TableCell>
                          <Badge className={plan.status === 'Active' ? 'bg-green-500' : plan.status === 'Cancelled' ? 'bg-red-500' : 'bg-yellow-500'}>
                            {plan.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="terminals">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {terminalsLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader>
                    <div className="h-6 w-32 animate-pulse rounded bg-muted" />
                  </CardHeader>
                  <CardContent>
                    <div className="h-4 w-24 animate-pulse rounded bg-muted" />
                    <div className="h-4 w-32 animate-pulse rounded bg-muted mt-2" />
                  </CardContent>
                </Card>
              ))
            ) : terminals.length === 0 ? (
              <div className="col-span-3 text-center py-8 text-muted-foreground">
                No payment terminals found
              </div>
            ) : (
              terminals.map((terminal) => (
                <Card key={terminal.id}>
                  <CardHeader>
                    <div className="flex justify-between items-center">
                      <CardTitle className="text-lg">{terminal.name}</CardTitle>
                      <Badge className={terminal.status === 'Online' ? 'bg-green-500' : 'bg-red-500'}>
                        {terminal.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{terminal.location}</p>
                    <p className="text-sm text-muted-foreground mt-1">Last: {terminal.lastTransaction}</p>
                    <div className="mt-4 flex gap-2">
                      <Button size="sm" variant="outline">Test</Button>
                      <Button size="sm" variant="outline">Settings</Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Payment Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">US Payment Processor</p>
                  <p className="text-sm text-muted-foreground">Stripe - Credit/Debit cards</p>
                </div>
                <Button variant="outline">
                  <Settings className="mr-2 h-4 w-4" />
                  Configure
                </Button>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">India Payment Processor</p>
                  <p className="text-sm text-muted-foreground">Razorpay - UPI, Paytm, PhonePe, Cards, Net Banking</p>
                </div>
                <Badge className="bg-green-500">Active</Badge>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">Accept Credit Cards</p>
                  <p className="text-sm text-muted-foreground">Visa, Mastercard, Amex, Discover</p>
                </div>
                <Button variant="outline">Enable</Button>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">Recurring Payments</p>
                  <p className="text-sm text-muted-foreground">Setup automatic billing</p>
                </div>
                <Button variant="outline">Enable</Button>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">Payment Receipts</p>
                  <p className="text-sm text-muted-foreground">Email receipts automatically</p>
                </div>
                <Button variant="outline">Configure</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Credit card payments must use provider-hosted Stripe Elements. */}
      <Dialog open={showCreditCardDialog} onOpenChange={setShowCreditCardDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Credit card payments unavailable</DialogTitle>
            <DialogDescription>
              Card entry is disabled until Stripe Elements is connected to a server-created PaymentIntent. No card number or CVV is collected by CoreDent.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setShowCreditCardDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>    </div>
  );
}