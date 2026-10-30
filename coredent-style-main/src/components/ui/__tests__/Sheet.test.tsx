import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "../sheet";

describe("Sheet", () => {
  it("renders SheetTrigger with children", () => {
    render(
      <Sheet>
        <SheetTrigger>Open Sheet</SheetTrigger>
      </Sheet>,
    );
    expect(screen.getByText("Open Sheet")).toBeInTheDocument();
  });

  it("renders SheetContent when open", () => {
    render(
      <Sheet defaultOpen>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>Sheet content</SheetContent>
      </Sheet>,
    );
    const content = screen.getByText("Sheet content");
    expect(content).toBeInTheDocument();
  });

  it("renders SheetHeader", () => {
    const { container } = render(<SheetHeader>Header content</SheetHeader>);
    const header = container.firstChild as HTMLElement;
    expect(header).toBeInTheDocument();
    expect(header).toHaveClass("flex");
    expect(header).toHaveClass("flex-col");
    expect(header).toHaveClass("space-y-2");
  });

  it("renders SheetFooter", () => {
    const { container } = render(<SheetFooter>Footer content</SheetFooter>);
    const footer = container.firstChild as HTMLElement;
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveClass("flex");
    expect(footer).toHaveClass("flex-col-reverse");
  });

  it("renders SheetTitle when open", () => {
    render(
      <Sheet defaultOpen>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>
          <SheetTitle>Sheet Title</SheetTitle>
        </SheetContent>
      </Sheet>
    );
    const title = screen.getByText("Sheet Title");
    expect(title).toBeInTheDocument();
  });

  it("renders SheetDescription when open", () => {
    render(
      <Sheet defaultOpen>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>
          <SheetDescription>Sheet description text</SheetDescription>
        </SheetContent>
      </Sheet>
    );
    const desc = screen.getByText("Sheet description text");
    expect(desc).toBeInTheDocument();
  });

  it("renders SheetClose button when open", () => {
    render(
      <Sheet defaultOpen>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>
          <SheetClose>Close</SheetClose>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getAllByText("Close").length).toBeGreaterThan(0);
  });

  it("applies custom className to SheetContent when open", () => {
    render(
      <Sheet defaultOpen>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent className="custom-class">Content</SheetContent>
      </Sheet>,
    );
    const content = screen.getByText("Content");
    expect(content).toHaveClass("custom-class");
  });
});
