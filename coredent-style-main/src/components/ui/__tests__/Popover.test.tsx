import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Popover, PopoverTrigger, PopoverContent } from "../popover";

describe("Popover", () => {
  it("renders PopoverTrigger with children", () => {
    render(
      <Popover>
        <PopoverTrigger>Open Popover</PopoverTrigger>
      </Popover>,
    );
    expect(screen.getByText("Open Popover")).toBeInTheDocument();
  });

  it("renders PopoverContent when open", () => {
    render(
      <Popover defaultOpen>
        <PopoverTrigger>Trigger</PopoverTrigger>
        <PopoverContent>Content here</PopoverContent>
      </Popover>,
    );
    const content = screen.getByText("Content here");
    expect(content).toBeInTheDocument();
  });

  it("applies custom className to PopoverContent", () => {
    render(
      <Popover defaultOpen>
        <PopoverTrigger>Trigger</PopoverTrigger>
        <PopoverContent className="custom-class">Content</PopoverContent>
      </Popover>,
    );
    const content = screen.getByText("Content");
    expect(content).toHaveClass("custom-class");
  });

  it("forwards additional props to PopoverContent", () => {
    render(
      <Popover defaultOpen>
        <PopoverTrigger>Trigger</PopoverTrigger>
        <PopoverContent data-testid="popover-content">Test content</PopoverContent>
      </Popover>,
    );
    expect(screen.getByTestId("popover-content")).toBeInTheDocument();
  });
});
