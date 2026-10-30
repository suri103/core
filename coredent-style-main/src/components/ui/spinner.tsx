import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SpinnerProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function Spinner({ className, size = 'md' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };

  return (
    <Loader2 
      className={cn(
        'animate-spin text-muted-foreground', 
        sizeClasses[size], 
        className
      )} 
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-[400px] h-screen w-full items-center justify-center bg-background/30 backdrop-blur-md">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-sm font-semibold text-muted-foreground animate-pulse">
          Loading booking portal...
        </p>
      </div>
    </div>
  );
}
