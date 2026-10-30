import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Progress } from "../progress";

describe("Progress", () => {
  it("renders with default props", () => {
    render(<Progress />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toBeInTheDocument();
    expect(progress).toHaveClass("relative");
    expect(progress).toHaveClass("h-4");
    expect(progress).toHaveClass("w-full");
    expect(progress).toHaveClass("rounded-full");
    expect(progress).toHaveClass("bg-secondary");
  });

  it("renders with value 0", () => {
    render(<Progress value={0} />);
    const indicator = screen.getByRole("progressbar").firstChild as HTMLElement;
    expect(indicator).toHaveStyle({ transform: "translateX(-100%)" });
  });

  it("renders with value 50", () => {
    render(<Progress value={50} />);
    const indicator = screen.getByRole("progressbar").firstChild as HTMLElement;
    expect(indicator).toHaveStyle({ transform: "translateX(-50%)" });
  });

  it("renders with value 100", () => {
    render(<Progress value={100} />);
    const indicator = screen.getByRole("progressbar").firstChild as HTMLElement;
    expect(indicator).toHaveStyle({ transform: "translateX(-0%)" });
  });

  it("applies custom className", () => {
    render(<Progress className="custom-class" />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveClass("custom-class");
    expect(progress).toHaveClass("bg-secondary");
  });

  it("has correct indicator classes", () => {
    render(<Progress value={75} />);
    const indicator = screen.getByRole("progressbar").firstChild as HTMLElement;
    expect(indicator).toHaveClass("h-full");
    expect(indicator).toHaveClass("w-full");
    expect(indicator).toHaveClass("bg-primary");
    expect(indicator).toHaveClass("transition-all");
  });

  it("renders with undefined value", () => {
    render(<Progress value={undefined} />);
    const indicator = screen.getByRole("progressbar").firstChild as HTMLElement;
    expect(indicator).toHaveStyle({ transform: "translateX(-100%)" });
  });
});
