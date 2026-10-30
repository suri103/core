import type { ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();

  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode | ((size: { width: number; height: number }) => ReactNode) }) => (
      <div data-testid="responsive-container" style={{ width: 800, height: 400 }}>
        {typeof children === 'function' ? children({ width: 800, height: 400 }) : children}
      </div>
    ),
  };
});

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from '../sidebar';
import {
  ChartContainer,
  ChartLegendContent,
  ChartStyle,
  ChartTooltipContent,
} from '../chart';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '../carousel';

const chartConfig = {
  revenue: { label: 'Revenue', color: '#2563eb' },
  production: { label: 'Production', theme: { light: '#10b981', dark: '#34d399' } },
};

describe('high-impact UI primitives', () => {
  it('renders and toggles the complete desktop sidebar composition', () => {
    const onOpenChange = vi.fn();
    render(
      <SidebarProvider defaultOpen onOpenChange={onOpenChange}>
        <Sidebar collapsible="icon">
          <SidebarHeader><SidebarInput aria-label="Sidebar search" /></SidebarHeader>
          <SidebarSeparator />
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Workspace</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton tooltip="Dashboard" isActive>Dashboard</SidebarMenuButton>
                    <SidebarMenuBadge>3</SidebarMenuBadge>
                  </SidebarMenuItem>
                  <SidebarMenuSkeleton showIcon />
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter>Footer</SidebarFooter>
          <SidebarRail />
        </Sidebar>
        <SidebarInset>
          <SidebarTrigger />
          <main>Page content</main>
        </SidebarInset>
      </SidebarProvider>,
    );

    expect(screen.getByText('Workspace')).toBeInTheDocument();
    const trigger = document.querySelector('[data-sidebar="trigger"]') as HTMLButtonElement;
    expect(trigger).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(onOpenChange).toHaveBeenCalledWith(false);
    fireEvent.keyDown(window, { key: 'b', ctrlKey: true });
    expect(onOpenChange).toHaveBeenCalled();
  });

  it('renders chart styles, tooltip variants, and legends through chart context', () => {
    const payload = [{
      dataKey: 'revenue',
      name: 'revenue',
      value: 1234,
      color: '#2563eb',
      payload: { fill: '#2563eb' },
    }];

    render(
      <ChartContainer config={chartConfig} id="finance">
        {(
          <div>
            <ChartStyle id="inline" config={chartConfig} />
            <ChartTooltipContent active label="Revenue" payload={payload} />
            <ChartTooltipContent active label="Revenue" payload={payload} indicator="line" hideIndicator />
            <ChartLegendContent payload={[{ value: 'revenue', dataKey: 'revenue', color: '#2563eb' }]} />
          </div>
        ) as never}
      </ChartContainer>,
    );

    expect(screen.getAllByText('Revenue').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1,234').length).toBeGreaterThan(0);
    expect(document.querySelector('style')).toHaveTextContent('--color-revenue: #2563eb');
  });

  it('renders horizontal and vertical carousel controls and keyboard navigation', () => {
    const setApi = vi.fn();
    const { rerender } = render(
      <Carousel setApi={setApi} aria-label="Featured patients">
        <CarouselContent>
          <CarouselItem>First slide</CarouselItem>
          <CarouselItem>Second slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>,
    );

    expect(screen.getByRole('region', { name: 'Featured patients' })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole('region'), { key: 'ArrowRight' });
    fireEvent.keyDown(screen.getByRole('region'), { key: 'ArrowLeft' });
    expect(screen.getByText('First slide')).toBeInTheDocument();

    rerender(
      <Carousel orientation="vertical">
        <CarouselContent><CarouselItem>Vertical slide</CarouselItem></CarouselContent>
        <CarouselPrevious /><CarouselNext />
      </Carousel>,
    );
    expect(screen.getByText('Vertical slide')).toBeInTheDocument();
  });
});