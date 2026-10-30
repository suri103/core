/**
 * Marketing Page
 *
 * Marketing campaign management is not backed by a production API yet. This
 * page intentionally shows an honest unavailable state rather than fabricated
 * campaign, patient, or revenue figures.
 */

import { BarChart3, Mail, Megaphone, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const plannedAreas = [
  {
    title: "Campaigns",
    description: "Email and SMS campaign delivery, scheduling, and consent-aware status tracking.",
    icon: Megaphone,
  },
  {
    title: "Patient segments",
    description: "Saved, tenant-scoped patient audiences with explainable criteria and counts.",
    icon: Users,
  },
  {
    title: "Templates",
    description: "Reusable communication templates with approval and unsubscribe controls.",
    icon: Mail,
  },
  {
    title: "Analytics",
    description: "Provider-backed delivery, engagement, and attributed-revenue reporting.",
    icon: BarChart3,
  },
];

export default function Marketing() {
  return (
    <div className="container mx-auto space-y-6 py-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">Marketing</h1>
          <Badge variant="outline">Not available</Badge>
        </div>
        <p className="text-muted-foreground">
          Campaigns, newsletters, and patient engagement will appear here when the marketing service is connected.
        </p>
      </div>

      <Card className="border-amber-200 bg-amber-50">
        <CardHeader>
          <CardTitle>Marketing is not implemented</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-amber-950">
          <p>No campaign, subscriber, patient-segment, engagement, or revenue data is available from the current backend.</p>
          <p>Creating campaigns and sending messages are disabled until a production API with consent, delivery tracking, and tenant isolation is deployed.</p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {plannedAreas.map(({ title, description, icon: Icon }) => (
          <Card key={title} className="border-dashed">
            <CardContent className="flex gap-4 p-6">
              <Icon className="mt-1 h-5 w-5 text-muted-foreground" />
              <div>
                <h2 className="font-semibold">{title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{description}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
