import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Slider } from "../slider";

describe("Slider", () => {
  it("renders correctly", () => {
    render(<Slider />);
    const slider = screen.getByRole("slider");
    expect(slider).toBeInTheDocument();
  });

  it("has correct root classes", () => {
    const { container } = render(<Slider />);
    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass("relative");
    expect(root).toHaveClass("flex");
    expect(root).toHaveClass("w-full");
    expect(root).toHaveClass("touch-none");
    expect(root).toHaveClass("select-none");
    expect(root).toHaveClass("items-center");
  });

  it("applies custom className", () => {
    const { container } = render(<Slider className="w-[200px]" />);
    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass("w-[200px]");
    expect(root).toHaveClass("relative");
  });

  it("renders with default value", () => {
    render(<Slider defaultValue={[50]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuenow", "50");
  });

  it("renders with min and max", () => {
    render(<Slider min={0} max={100} defaultValue={[25]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuemin", "0");
    expect(slider).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders with step", () => {
    render(<Slider step={10} defaultValue={[50]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuenow", "50");
  });

  it("renders with multiple values", () => {
    const { container } = render(<Slider defaultValue={[25, 75]} />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("has thumb with correct classes", () => {
    const { container } = render(<Slider defaultValue={[50]} />);
    const thumb = container.querySelector('[role="slider"]');
    expect(thumb).toHaveClass("h-5");
    expect(thumb).toHaveClass("w-5");
    expect(thumb).toHaveClass("rounded-full");
    expect(thumb).toHaveClass("border-2");
    expect(thumb).toHaveClass("border-primary");
    expect(thumb).toHaveClass("bg-background");
  });

  it("has track with correct classes", () => {
    const { container } = render(<Slider defaultValue={[50]} />);
    const root = container.firstChild as HTMLElement;
    const track = root.querySelector('span');
    expect(track).toHaveClass("relative");
    expect(track).toHaveClass("h-2");
    expect(track).toHaveClass("w-full");
    expect(track).toHaveClass("grow");
    expect(track).toHaveClass("overflow-hidden");
    expect(track).toHaveClass("rounded-full");
    expect(track).toHaveClass("bg-secondary");
  });

  it("has range with correct classes", () => {
    const { container } = render(<Slider defaultValue={[50]} />);
    const root = container.firstChild as HTMLElement;
    const range = root.querySelector('.bg-primary.absolute');
    expect(range).toHaveClass("absolute");
    expect(range).toHaveClass("h-full");
    expect(range).toHaveClass("bg-primary");
  });

  it("is disabled when disabled prop is true", () => {
    render(<Slider disabled defaultValue={[50]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("data-disabled");
  });
});
