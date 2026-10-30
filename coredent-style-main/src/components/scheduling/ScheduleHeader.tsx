import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  Search, 
  Calendar as CalendarIcon 
} from 'lucide-react';

interface ScheduleHeaderProps {
  formattedDate: string;
  currentDate: Date;
  view: 'day' | 'week' | 'month';
  onViewChange: (view: 'day' | 'week' | 'month') => void;
  onPrevious: () => void;
  onNext: () => void;
  onToday: () => void;
  onDateSelect: (date: Date) => void;
  onNewAppointment: () => void;
  onOpenSearch: () => void;
}

export function ScheduleHeader({
  formattedDate,
  currentDate,
  view,
  onViewChange,
  onPrevious,
  onNext,
  onToday,
  onDateSelect,
  onNewAppointment,
  onOpenSearch,
}: ScheduleHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 border-b bg-card rounded-t-lg">
      {/* Date Navigation & Picker */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 mr-2">
          <Button variant="outline" size="icon" onClick={onPrevious} title="Previous">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={onToday}>
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={onNext} title="Next">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 text-lg font-semibold px-2 hover:bg-accent hover:text-accent-foreground">
              <CalendarIcon className="h-4 w-4 text-muted-foreground" />
              <span>{formattedDate}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="single"
              selected={currentDate}
              onSelect={(date) => date && onDateSelect(date)}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>

      {/* View Toggles & Actions */}
      <div className="flex flex-wrap items-center gap-3">
        {/* View Toggle tabs */}
        <Tabs 
          value={view} 
          onValueChange={(val) => onViewChange(val as 'day' | 'week' | 'month')}
        >
          <TabsList>
            <TabsTrigger value="day">Day</TabsTrigger>
            <TabsTrigger value="week">Week</TabsTrigger>
            <TabsTrigger value="month">Month</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onOpenSearch} className="flex items-center gap-1">
            <Search className="h-4 w-4" />
            <span className="hidden sm:inline">Search Patient</span>
          </Button>
          <Button size="sm" onClick={onNewAppointment} className="flex items-center gap-1">
            <Plus className="h-4 w-4" />
            <span>New Appointment</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
