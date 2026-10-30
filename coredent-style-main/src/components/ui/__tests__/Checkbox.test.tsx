import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Checkbox } from "../checkbox";

describe("Checkbox", () => {
  it("renders checkbox input", () => {
    render(<Checkbox aria-label="Accept terms" />);
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
  });

  it("applies default styles", () => {
    render(<Checkbox aria-label="Test" data-testid="cb" />);
    const cb = screen.getByTestId("cb");
    expect(cb).toHaveClass("h-4");
    expect(cb).toHaveClass("w-4");
    expect(cb).toHaveClass("rounded-sm");
    expect(cb).toHaveClass("border-primary");
  });

  it("can be checked", () => {
    render(<Checkbox checked={true} aria-label="Checked" />);
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("can be unchecked", () => {
    render(<Checkbox checked={false} aria-label="Unchecked" />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("supports disabled state", () => {
    render(<Checkbox disabled aria-label="Disabled" />);
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByRole("checkbox")).toHaveClass("disabled:cursor-not-allowed");
  });

  it("merges custom className", () => {
    render(<Checkbox aria-label="Custom" className="custom-class" data-testid="cb" />);
    const cb = screen.getByTestId("cb");
    expect(cb).toHaveClass("custom-class");
    expect(cb).toHaveClass("h-4");
  });
});
