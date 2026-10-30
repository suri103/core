
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Pill, ShieldAlert, Loader2 } from 'lucide-react';

interface EPrescribeModalProps {
  isOpen: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
}

export function EPrescribeModal({ isOpen, onClose, patientName }: EPrescribeModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[900px] h-[80vh] flex flex-col p-0 overflow-hidden rounded-3xl">
        <DialogHeader className="p-6 pb-4 border-b border-slate-100 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
              <Pill className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-xl font-black text-slate-800 tracking-tight">
                e-Prescribing (eRx) for {patientName}
              </DialogTitle>
              <DialogDescription className="text-slate-500 font-medium">
                Secure integration powered by DoseSpot / Surescripts
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        
        <div className="flex-1 bg-slate-50 relative">
          {/* 
            In a real implementation, this iframe would point to an SSO URL 
            generated securely by the backend API:
            src={`https://my.dosespot.com/Login.aspx?b=...&SingleSignOnUserId=...`}
          */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8 z-10">
            <ShieldAlert className="w-16 h-16 text-indigo-200 mb-4" />
            <h3 className="text-2xl font-black text-slate-700 mb-2">SSO Integration Required</h3>
            <p className="text-slate-500 max-w-md mx-auto mb-6">
              To send real electronic prescriptions, the provider must undergo identity proofing (EPCS). 
              This iframe securely hosts the DoseSpot widget once API keys are configured.
            </p>
            <div className="flex items-center gap-2 text-sm font-bold text-indigo-600 bg-indigo-50 px-4 py-2 rounded-xl">
              <Loader2 className="w-4 h-4 animate-spin" />
              Waiting for production API keys...
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
