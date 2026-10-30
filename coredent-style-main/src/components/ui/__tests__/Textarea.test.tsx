import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Textarea } from "../textarea";

describe("Textarea", () => {
  it("renders correctly", () => {
    render(<Textarea />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("has default textarea classes", () => {
    render(<Textarea />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveClass("flex");
    expect(textarea).toHaveClass("min-h-[80px]");
    expect(textarea).toHaveClass("w-full");
    expect(textarea).toHaveClass("rounded-md");
    expect(textarea).toHaveClass("border");
    expect(textarea).toHaveClass("border-input");
    expect(textarea).toHaveClass("bg-background");
    expect(textarea).toHaveClass("px-3");
    expect(textarea).toHaveClass("py-2");
    expect(textarea).toHaveClass("text-sm");
  });

  it("applies custom className", () => {
    render(<Textarea className="custom-class" />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveClass("custom-class");
    expect(textarea).toHaveClass("min-h-[80px]");
  });

  it("renders placeholder text", () => {
    render(<Textarea placeholder="Enter your message" />);
    const textarea = screen.getByPlaceholderText("Enter your message");
    expect(textarea).toBeInTheDocument();
  });

  it("displays value correctly", () => {
    render(<Textarea value="Hello World" readOnly />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("Hello World");
  });

  it("is disabled when disabled prop is true", () => {
    render(<Textarea disabled />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveClass("disabled:cursor-not-allowed");
    expect(textarea).toHaveClass("disabled:opacity-50");
  });

  it("calls onChange when typed into", () => {
    const handleChange = vi.fn();
    render(<Textarea onChange={handleChange} />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "New text" } });
    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  it("supports rows attribute", () => {
    render(<Textarea rows={5} />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveAttribute("rows", "5");
  });

  it("supports maxLength attribute", () => {
    render(<Textarea maxLength={100} />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveAttribute("maxLength", "100");
  });

  it("supports required attribute", () => {
    render(<Textarea required />);
    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeRequired();
  });

  it("forwards ref correctly", () => {
    const ref = vi.fn();
    render(<Textarea ref={ref} />);
    expect(ref).toHaveBeenCalled();
  });
});
