import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Switch } from "../switch";

describe("Switch", () => {
  it("renders correctly", () => {
    render(<Switch />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toBeInTheDocument();
  });

  it("is unchecked by default", () => {
    render(<Switch />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).not.toBeChecked();
    expect(switchEl).toHaveAttribute("data-state", "unchecked");
  });

  it("can be checked", () => {
    render(<Switch defaultChecked />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toBeChecked();
    expect(switchEl).toHaveAttribute("data-state", "checked");
  });

  it("toggles when clicked", () => {
    render(<Switch />);
    const switchEl = screen.getByRole("switch");
    fireEvent.click(switchEl);
    expect(switchEl).toBeChecked();
    expect(switchEl).toHaveAttribute("data-state", "checked");
  });

  it("applies custom className", () => {
    render(<Switch className="custom-class" />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toHaveClass("custom-class");
    expect(switchEl).toHaveClass("peer");
    expect(switchEl).toHaveClass("inline-flex");
  });

  it("has correct unchecked styles", () => {
    render(<Switch />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toHaveClass("data-[state=unchecked]:bg-input");
  });

  it("has correct checked styles", () => {
    render(<Switch defaultChecked />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toHaveClass("data-[state=checked]:bg-primary");
  });

  it("is disabled when disabled prop is true", () => {
    render(<Switch disabled />);
    const switchEl = screen.getByRole("switch");
    expect(switchEl).toBeDisabled();
    expect(switchEl).toHaveClass("disabled:cursor-not-allowed");
    expect(switchEl).toHaveClass("disabled:opacity-50");
  });

  it("calls onCheckedChange when toggled", () => {
    const handleChange = vi.fn();
    render(<Switch onCheckedChange={handleChange} />);
    const switchEl = screen.getByRole("switch");
    fireEvent.click(switchEl);
    expect(handleChange).toHaveBeenCalledWith(true);
  });

  it("renders with thumb element", () => {
    render(<Switch />);
    const switchEl = screen.getByRole("switch");
    const thumb = switchEl.firstChild as HTMLElement;
    expect(thumb).toHaveClass("h-5");
    expect(thumb).toHaveClass("w-5");
    expect(thumb).toHaveClass("rounded-full");
    expect(thumb).toHaveClass("bg-background");
  });
});
