import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Label } from "../label";

describe("Label", () => {
  it("renders label text", () => {
    render(<Label>Label Text</Label>);
    expect(screen.getByText("Label Text")).toBeInTheDocument();
  });

  it("applies base styles", () => {
    render(<Label data-testid="label">Styled Label</Label>);
    const label = screen.getByTestId("label");
    expect(label).toHaveClass("text-sm");
    expect(label).toHaveClass("font-medium");
  });

  it("renders htmlFor attribute", () => {
    render(<Label htmlFor="input-id" data-testid="label">Input Label</Label>);
    expect(screen.getByTestId("label")).toHaveAttribute("for", "input-id");
  });

  it("merges custom className", () => {
    render(<Label className="custom-class" data-testid="label">Custom</Label>);
    const label = screen.getByTestId("label");
    expect(label).toHaveClass("custom-class");
    expect(label).toHaveClass("text-sm");
  });

  it("renders as label element", () => {
    render(<Label>Test Label</Label>);
    expect(screen.getByText("Test Label")).toBeInstanceOf(HTMLLabelElement);
  });
});
