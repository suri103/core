import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AspectRatio } from "../aspect-ratio";
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbEllipsis,
} from "../breadcrumb";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "../collapsible";
import { HoverCard, HoverCardTrigger, HoverCardContent } from "../hover-card";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "../resizable";
import { Toggle } from "../toggle";
import { ToggleGroup, ToggleGroupItem } from "../toggle-group";
import { Spinner, PageLoader } from "../spinner";
import { DemoBanner } from "../demo-banner";

describe("ui: aspect-ratio", () => {
  it("renders children inside the aspect ratio container", () => {
    const { container } = render(
      <AspectRatio ratio={16 / 9}>
        <img alt="test" src="x" />
      </AspectRatio>,
    );
    expect(container.querySelector("img")).toBeTruthy();
  });
});

describe("ui: breadcrumb", () => {
  it("renders a breadcrumb trail with a current page", () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">Home</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Patients</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(
      screen.getByRole("navigation", { name: "breadcrumb" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Patients")).toHaveAttribute("aria-current", "page");
  });

  it("renders an ellipsis with a More label", () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbEllipsis />
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByText("More")).toBeInTheDocument();
  });

  it("supports asChild links via Slot", () => {
    render(
      <BreadcrumbLink asChild>
        <a href="/x">SlotLink</a>
      </BreadcrumbLink>,
    );
    expect(screen.getByText("SlotLink")).toHaveAttribute("href", "/x");
  });

  it("renders a custom separator when provided", () => {
    render(<BreadcrumbSeparator>{">"}</BreadcrumbSeparator>);
    expect(screen.getByText(">")).toBeInTheDocument();
  });
});

describe("ui: collapsible", () => {
  it("toggles content visibility", async () => {
    const user = userEvent.setup();
    render(
      <Collapsible defaultOpen>
        <CollapsibleTrigger>Toggle</CollapsibleTrigger>
        <CollapsibleContent>Secret content</CollapsibleContent>
      </Collapsible>,
    );
    expect(screen.getByText("Toggle")).toBeInTheDocument();
    expect(screen.getByText("Secret content")).toBeInTheDocument();
    await user.click(screen.getByText("Toggle"));
  });
});

describe("ui: hover-card", () => {
  it("renders the trigger and shows content on hover", async () => {
    const user = userEvent.setup();
    render(
      <HoverCard>
        <HoverCardTrigger asChild>
          <button>Hover me</button>
        </HoverCardTrigger>
        <HoverCardContent>Hovered content</HoverCardContent>
      </HoverCard>,
    );
    expect(screen.getByText("Hover me")).toBeInTheDocument();
    await user.hover(screen.getByText("Hover me"));
    expect(await screen.findByText("Hovered content")).toBeInTheDocument();
  });

  it("applies align and sideOffset defaults", () => {
    render(
      <HoverCard open>
        <HoverCardTrigger asChild>
          <button>x</button>
        </HoverCardTrigger>
        <HoverCardContent align="start" sideOffset={8}>
          content
        </HoverCardContent>
      </HoverCard>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });
});

describe("ui: resizable", () => {
  it("renders panels and a handle", () => {
    const { container } = render(
      <ResizablePanelGroup direction="horizontal">
        <ResizablePanel>One</ResizablePanel>
        <ResizableHandle />
        <ResizablePanel>Two</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
    expect(container.querySelector('[data-panel-resize-handle-id]')).toBeTruthy();
  });

  it("renders the handle grip when withHandle is set", () => {
    const { container } = render(
      <ResizablePanelGroup direction="horizontal">
        <ResizablePanel>One</ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel>Two</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(container.querySelector('[data-panel-resize-handle-id]')).toBeTruthy();
  });
});

describe("ui: toggle", () => {
  it("toggles pressed state on click", async () => {
    const user = userEvent.setup();
    const onPressedChange = vi.fn();
    render(
      <Toggle aria-label="Bold" onPressedChange={onPressedChange}>
        B
      </Toggle>,
    );
    await user.click(screen.getByLabelText("Bold"));
    expect(onPressedChange).toHaveBeenCalledWith(true);
  });

  it("applies variant and size classes", () => {
    render(
      <Toggle variant="outline" size="lg" aria-label="x">
        x
      </Toggle>,
    );
    expect(screen.getByLabelText("x")).toBeInTheDocument();
  });
});

describe("ui: toggle-group", () => {
  it("renders items and reports value changes", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <ToggleGroup type="single" onValueChange={onValueChange}>
        <ToggleGroupItem value="a">A</ToggleGroupItem>
        <ToggleGroupItem value="b">B</ToggleGroupItem>
      </ToggleGroup>,
    );
    await user.click(screen.getByText("A"));
    expect(onValueChange).toHaveBeenCalledWith("a");
  });

  it("items inherit variant from the group context", () => {
    render(
      <ToggleGroup type="single" variant="outline" size="sm">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});

describe("ui: spinner", () => {
  it("renders the spinner with the configured size class", () => {
    const { container } = render(<Spinner size="lg" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toMatch(/h-8/);
  });

  it("defaults to the md size", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toMatch(/h-6/);
  });

  it("renders the full page loader with a label", () => {
    render(<PageLoader />);
    expect(screen.getByText("Loading booking portal...")).toBeInTheDocument();
  });
});

describe("ui: demo-banner", () => {
  it("renders the demo mode notice", () => {
    render(<DemoBanner />);
    expect(screen.getByText(/Demo Mode/i)).toBeInTheDocument();
    expect(
      screen.getByText(/sample data for demonstration purposes/i),
    ).toBeInTheDocument();
  });
});
