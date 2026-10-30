import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Separator } from "../separator";

describe("Separator", () => {
  it("renders horizontal separator by default", () => {
    const { container } = render(<Separator />);
    const separator = container.firstChild as HTMLElement;
    expect(separator).toBeInTheDocument();
    expect(separator).toHaveClass("shrink-0");
    expect(separator).toHaveClass("bg-border");
    expect(separator).toHaveClass("h-[1px]");
    expect(separator).toHaveClass("w-full");
  });

  it("renders vertical separator", () => {
    const { container } = render(<Separator orientation="vertical" />);
    const separator = container.firstChild as HTMLElement;
    expect(separator).toHaveClass("h-full");
    expect(separator).toHaveClass("w-[1px]");
  });

  it("applies custom className", () => {
    const { container } = render(<Separator className="my-4" />);
    const separator = container.firstChild as HTMLElement;
    expect(separator).toHaveClass("my-4");
    expect(separator).toHaveClass("bg-border");
  });

  it("forwards additional props", () => {
    render(<Separator data-testid="custom-separator" />);
    expect(screen.getByTestId("custom-separator")).toBeInTheDocument();
  });
});
