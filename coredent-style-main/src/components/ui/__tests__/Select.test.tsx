import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel } from "../select";

describe("Select", () => {
  it("renders SelectTrigger with placeholder", () => {
    render(
      <Select>
        <SelectTrigger data-testid="select-trigger">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="1">Option 1</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByTestId("select-trigger")).toBeInTheDocument();
    expect(screen.getByText("Select an option")).toBeInTheDocument();
  });

  it("applies base SelectTrigger styles", () => {
    render(
      <Select>
        <SelectTrigger data-testid="select-trigger">
          <SelectValue placeholder="Select" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="1">Option</SelectItem>
        </SelectContent>
      </Select>,
    );
    const trigger = screen.getByTestId("select-trigger");
    expect(trigger).toHaveClass("flex");
    expect(trigger).toHaveClass("h-10");
    expect(trigger).toHaveClass("rounded-md");
    expect(trigger).toHaveClass("border-input");
  });

  it("renders SelectContent", () => {
    render(
      <Select open={true}>
        <SelectTrigger>
          <SelectValue placeholder="Select" />
        </SelectTrigger>
        <SelectContent data-testid="select-content">
          <SelectItem value="1">Option 1</SelectItem>
          <SelectItem value="2">Option 2</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByTestId("select-content")).toBeInTheDocument();
  });

  it("renders SelectItem with correct value", () => {
    render(
      <Select open={true}>
        <SelectTrigger>
          <SelectValue placeholder="Select" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="test-value" data-testid="select-item">Test Option</SelectItem>
        </SelectContent>
      </Select>,
    );
    const item = screen.getByTestId("select-item");
    expect(item).toBeInTheDocument();
    expect(screen.getByText("Test Option")).toBeInTheDocument();
  });

  it("renders SelectGroup with label", () => {
    render(
      <Select open={true}>
        <SelectTrigger>
          <SelectValue placeholder="Select" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Group Label</SelectLabel>
            <SelectItem value="1">Item</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByText("Group Label")).toBeInTheDocument();
  });

  it("supports disabled state", () => {
    render(
      <Select>
        <SelectTrigger disabled data-testid="select-trigger">
          <SelectValue placeholder="Disabled" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="1">Option</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByTestId("select-trigger")).toHaveClass("disabled:cursor-not-allowed");
  });
});
