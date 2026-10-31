import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  Search, 
  Calendar as CalendarIcon,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

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
  isLoading?: boolean;
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
  isLoading = false,
}: ScheduleHeaderProps) {
  // Check if current view matches today
  const isCurrentViewToday = useMemo(() => {
    const today = new Date();
    if (view === 'day') {
      return (
        currentDate.getDate() === today.getDate() &&
        currentDate.getMonth() === today.getMonth() &&
        currentDate.getFullYear() === today.getFullYear()
      );
    }
    if (view === 'week') {
      const day = currentDate.getDay();
      const start = new Date(currentDate);
      start.setDate(currentDate.getDate() - day);
      start.setHours(0, 0, 0, 0);
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      end.setHours(23, 59, 59, 999);
      return today >= start && today <= end;
    }
    if (view === 'month') {
      return (
        currentDate.getMonth() === today.getMonth() &&
        currentDate.getFullYear() === today.getFullYear()
      );
    }
    return false;
  }, [currentDate, view]);

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 border-b bg-card rounded-t-lg">
      {/* Date Navigation & Picker */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 mr-1">
          <Button variant="outline" size="icon" onClick={onPrevious} title="Previous">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant={isCurrentViewToday ? 'secondary' : 'outline'}
            size="sm"
            onClick={onToday}
            disabled={isCurrentViewToday}
            title={isCurrentViewToday ? 'Currently viewing today' : 'Jump to Today'}
            className={cn(
              'text-xs font-semibold px-3 transition-colors',
              isCurrentViewToday ? 'opacity-60 cursor-default' : 'hover:bg-accent hover:text-accent-foreground font-medium'
            )}
          >
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={onNext} title="Next">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="ghost"
                className="flex items-center gap-2 text-base sm:text-lg font-semibold px-2 hover:bg-accent hover:text-accent-foreground"
              >
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

          {isCurrentViewToday && (
            <Badge
              variant="secondary"
              className="bg-primary/10 text-primary border-primary/20 text-[11px] font-semibold hidden sm:inline-flex"
            >
              {view === 'day' ? 'Today' : view === 'week' ? 'This Week' : 'This Month'}
            </Badge>
          )}

          {isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground ml-1" />
          )}
        </div>
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
