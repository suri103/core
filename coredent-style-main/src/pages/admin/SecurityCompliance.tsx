import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  ShieldCheck, 
  FileSignature, 
  FileWarning, 
  ServerCrash,
  CheckCircle2,
  AlertTriangle,
  Download
} from "lucide-react";

export default function SecurityCompliance() {
  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Security & Compliance</h1>
          <p className="text-muted-foreground">Manage HIPAA SRA, BAAs, and IT security protocols.</p>
        </div>
        <Button>
          <ShieldCheck className="h-4 w-4 mr-2" />
          Run SRA Audit
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* BAAs Card */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="space-y-1">
                <CardTitle className="text-lg">Business Associate Agreements (BAAs)</CardTitle>
                <CardDescription>Signed vendor compliance</CardDescription>
              </div>
              <div className="p-2 bg-blue-100 text-blue-600 rounded-lg">
                <FileSignature className="h-5 w-5" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between border-b pb-2">
              <div>
                <p className="font-medium">AWS / S3 Storage</p>
                <p className="text-xs text-muted-foreground">Signed: Jan 15, 2026</p>
              </div>
              <Badge className="bg-green-100 text-green-700 border-none">Active</Badge>
            </div>
            <div className="flex items-center justify-between border-b pb-2">
              <div>
                <p className="font-medium">Twilio (SMS)</p>
                <p className="text-xs text-muted-foreground">Signed: Jan 20, 2026</p>
              </div>
              <Badge className="bg-green-100 text-green-700 border-none">Active</Badge>
            </div>
            <div className="flex items-center justify-between pb-2">
              <div>
                <p className="font-medium">DentalXChange</p>
                <p className="text-xs text-muted-foreground">Pending Signature</p>
              </div>
              <Badge variant="destructive">Missing</Badge>
            </div>
            <Button variant="outline" className="w-full">Upload New BAA</Button>
          </CardContent>
        </Card>

        {/* Security Risk Assessment */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="space-y-1">
                <CardTitle className="text-lg">HIPAA SRA</CardTitle>
                <CardDescription>Security Risk Assessment</CardDescription>
              </div>
              <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg">
                <FileWarning className="h-5 w-5" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span className="text-sm">Workstation Use & Security</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span className="text-sm">Device & Media Controls</span>
              </div>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium">Access Control (MFA Enforced)</span>
              </div>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium">Audit Controls (Log Review)</span>
              </div>
            </div>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-xs text-amber-800 font-medium">Annual SRA is due in 45 days. Schedule your compliance review.</p>
            </div>
          </CardContent>
        </Card>

        {/* DR & Pen Testing */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="space-y-1">
                <CardTitle className="text-lg">Disaster Recovery & Pentesting</CardTitle>
                <CardDescription>Infrastructure auditing</CardDescription>
              </div>
              <div className="p-2 bg-slate-100 text-slate-600 rounded-lg">
                <ServerCrash className="h-5 w-5" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 border rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <h4 className="font-semibold text-sm">Disaster Recovery Test</h4>
                <Badge className="bg-green-100 text-green-700 border-none">Pass</Badge>
              </div>
              <p className="text-xs text-muted-foreground mb-3">Database restored from snapshot in 4.2 minutes.</p>
              <Button variant="secondary" size="sm" className="w-full">
                <Download className="h-4 w-4 mr-2" />
                Download Report
              </Button>
            </div>
            
            <div className="p-4 border rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <h4 className="font-semibold text-sm">Q1 Penetration Test</h4>
                <Badge variant="outline">Scheduled</Badge>
              </div>
              <p className="text-xs text-muted-foreground mb-3">Vendor: SecureTech Partners. Target: API endpoints.</p>
              <Button variant="secondary" size="sm" className="w-full" disabled>
                <Download className="h-4 w-4 mr-2" />
                Report Pending
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
