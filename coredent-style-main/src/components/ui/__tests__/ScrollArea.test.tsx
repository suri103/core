import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScrollArea } from "../scroll-area";

describe("ScrollArea", () => {
  it("renders with children", () => {
    render(
      <ScrollArea>
        <div>Scrollable content</div>
      </ScrollArea>,
    );
    expect(screen.getByText("Scrollable content")).toBeInTheDocument();
  });

  it("has correct root classes", () => {
    const { container } = render(
      <ScrollArea>
        <div>Content</div>
      </ScrollArea>,
    );
    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass("relative");
    expect(root).toHaveClass("overflow-hidden");
  });

  it("applies custom className to root", () => {
    const { container } = render(
      <ScrollArea className="h-[200px] w-[300px]">
        <div>Content</div>
      </ScrollArea>,
    );
    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass("h-[200px]");
    expect(root).toHaveClass("w-[300px]");
  });

  it("forwards ref to ScrollArea", () => {
    const ref = { current: null };
    render(
      <ScrollArea ref={ref}>
        <div>Content</div>
      </ScrollArea>,
    );
    expect(ref.current).not.toBeNull();
  });
});
