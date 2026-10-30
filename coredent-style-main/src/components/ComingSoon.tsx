import { Construction } from 'lucide-react';

interface ComingSoonProps {
  pageName: string;
  description?: string;
}

export function ComingSoon({ pageName, description }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center bg-background border rounded-xl m-4">
      <div className="p-4 bg-amber-100 dark:bg-amber-900/30 rounded-full mb-6">
        <Construction className="h-12 w-12 text-amber-600 dark:text-amber-400" />
      </div>
      <h2 className="text-2xl font-bold mb-2 text-foreground">{pageName}</h2>
      <p className="text-muted-foreground mb-4 max-w-md">
        {description || `This feature is coming soon. We're working hard to bring you a full ${pageName.toLowerCase()} experience.`}
      </p>
      <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary rounded-full text-sm font-medium">
        <span className="h-2 w-2 bg-green-500 rounded-full animate-pulse" />
        In Development
      </div>
    </div>
  );
}
