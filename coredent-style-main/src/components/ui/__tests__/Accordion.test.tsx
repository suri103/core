import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "../accordion";

describe("Accordion", () => {
  it("renders with items", () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item 1</AccordionTrigger>
          <AccordionContent>Content 1</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    expect(screen.getByText("Item 1")).toBeInTheDocument();
  });

  it("renders AccordionItem with border", () => {
    const { container } = render(
      <Accordion type="single">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const item = container.querySelector('[data-state]');
    expect(item).toHaveClass("border-b");
  });

  it("renders AccordionTrigger with chevron", () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1">
          <AccordionTrigger>Click me</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const trigger = screen.getByText("Click me");
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveClass("flex");
    expect(trigger).toHaveClass("flex-1");
    expect(trigger).toHaveClass("items-center");
    expect(trigger).toHaveClass("justify-between");
    expect(trigger).toHaveClass("py-4");
    expect(trigger).toHaveClass("font-medium");
    expect(trigger).toHaveClass("hover:underline");
  });

  it("renders AccordionContent when open", () => {
    render(
      <Accordion type="single" defaultValue="item-1">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item</AccordionTrigger>
          <AccordionContent>Hidden content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const content = screen.getByText("Hidden content");
    expect(content).toBeInTheDocument();
  });

  it("applies custom className to AccordionItem", () => {
    const { container } = render(
      <Accordion type="single">
        <AccordionItem value="item-1" className="custom-class">
          <AccordionTrigger>Item</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const item = container.querySelector('[data-state]');
    expect(item).toHaveClass("custom-class");
    expect(item).toHaveClass("border-b");
  });

  it("applies custom className to AccordionTrigger", () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1">
          <AccordionTrigger className="custom-trigger">Item</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const trigger = screen.getByText("Item");
    expect(trigger).toHaveClass("custom-trigger");
  });

  it("applies custom className to AccordionContent", () => {
    render(
      <Accordion type="single" defaultValue="item-1">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item</AccordionTrigger>
          <AccordionContent className="custom-content">Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const content = screen.getByText("Content");
    expect(content).toHaveClass("custom-content");
  });

  it("renders ChevronDown icon", () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const chevron = screen.getByText("Item").closest("button")?.querySelector("svg");
    expect(chevron).toHaveClass("h-4");
    expect(chevron).toHaveClass("w-4");
    expect(chevron).toHaveClass("shrink-0");
    expect(chevron).toHaveClass("transition-transform");
  });

  it("supports multiple items", () => {
    render(
      <Accordion type="multiple">
        <AccordionItem value="item-1">
          <AccordionTrigger>Item 1</AccordionTrigger>
          <AccordionContent>Content 1</AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-2">
          <AccordionTrigger>Item 2</AccordionTrigger>
          <AccordionContent>Content 2</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("Item 2")).toBeInTheDocument();
  });
});
