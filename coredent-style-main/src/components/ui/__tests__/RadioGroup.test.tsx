import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RadioGroup, RadioGroupItem } from "../radio-group";

describe("RadioGroup", () => {
  it("renders with items", () => {
    render(
      <RadioGroup defaultValue="option1">
        <RadioGroupItem value="option1" id="option1" />
        <RadioGroupItem value="option2" id="option2" />
      </RadioGroup>,
    );
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
  });

  it("has correct grid classes", () => {
    render(
      <RadioGroup>
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const group = screen.getByRole("radiogroup");
    expect(group).toHaveClass("grid");
    expect(group).toHaveClass("gap-2");
  });

  it("applies custom className to RadioGroup", () => {
    render(
      <RadioGroup className="custom-class">
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const group = screen.getByRole("radiogroup");
    expect(group).toHaveClass("custom-class");
    expect(group).toHaveClass("grid");
  });

  it("renders RadioGroupItem with correct classes", () => {
    render(
      <RadioGroup>
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const item = screen.getByRole("radio");
    expect(item).toHaveClass("aspect-square");
    expect(item).toHaveClass("h-4");
    expect(item).toHaveClass("w-4");
    expect(item).toHaveClass("rounded-full");
    expect(item).toHaveClass("border");
    expect(item).toHaveClass("border-primary");
  });

  it("renders RadioGroupItem as unchecked by default", () => {
    render(
      <RadioGroup>
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const item = screen.getByRole("radio");
    expect(item).not.toBeChecked();
  });

  it("renders checked item when value matches", () => {
    render(
      <RadioGroup defaultValue="opt1">
        <RadioGroupItem value="opt1" id="opt1" />
        <RadioGroupItem value="opt2" id="opt2" />
      </RadioGroup>,
    );
    const checkedItem = screen.getByRole("radio", { checked: true });
    expect(checkedItem).toHaveValue("opt1");
  });

  it("is disabled when disabled prop is true", () => {
    render(
      <RadioGroup disabled>
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const item = screen.getByRole("radio");
    expect(item).toBeDisabled();
    expect(item).toHaveClass("disabled:cursor-not-allowed");
    expect(item).toHaveClass("disabled:opacity-50");
  });

  it("renders with Circle icon indicator", () => {
    render(
      <RadioGroup defaultValue="opt1">
        <RadioGroupItem value="opt1" id="opt1" />
      </RadioGroup>,
    );
    const indicator = screen.getByRole("radio").querySelector("svg");
    expect(indicator).toHaveClass("h-2.5");
    expect(indicator).toHaveClass("w-2.5");
  });

  it("supports multiple options", () => {
    render(
      <RadioGroup defaultValue="small">
        <RadioGroupItem value="small" id="small" />
        <RadioGroupItem value="medium" id="medium" />
        <RadioGroupItem value="large" id="large" />
      </RadioGroup>,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });
});
