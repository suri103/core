import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Avatar, AvatarImage, AvatarFallback } from "../avatar";

describe("Avatar", () => {
  it("renders correctly", () => {
    const { container } = render(<Avatar />);
    const avatar = container.firstChild as HTMLElement;
    expect(avatar).toBeInTheDocument();
    expect(avatar).toHaveClass("relative");
    expect(avatar).toHaveClass("flex");
    expect(avatar).toHaveClass("h-10");
    expect(avatar).toHaveClass("w-10");
    expect(avatar).toHaveClass("shrink-0");
    expect(avatar).toHaveClass("overflow-hidden");
    expect(avatar).toHaveClass("rounded-full");
  });

  it("applies custom className", () => {
    const { container } = render(<Avatar className="h-12 w-12" />);
    const avatar = container.firstChild as HTMLElement;
    expect(avatar).toHaveClass("h-12");
    expect(avatar).toHaveClass("w-12");
    expect(avatar).toHaveClass("rounded-full");
  });

  it("renders AvatarImage (hidden until load in jsdom)", () => {
    const { container } = render(
      <Avatar>
        <AvatarImage src="/test-avatar.png" alt="Test User" />
      </Avatar>,
    );
    // In jsdom, image load events don't fire, so AvatarImage stays hidden
    // Verify the avatar root renders
    expect(container.firstChild).toBeInTheDocument();
  });

  it("renders AvatarFallback correctly", () => {
    render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    const fallback = screen.getByText("JD");
    expect(fallback).toBeInTheDocument();
    expect(fallback).toHaveClass("flex");
    expect(fallback).toHaveClass("h-full");
    expect(fallback).toHaveClass("w-full");
    expect(fallback).toHaveClass("items-center");
    expect(fallback).toHaveClass("justify-center");
    expect(fallback).toHaveClass("rounded-full");
    expect(fallback).toHaveClass("bg-muted");
  });

  it("renders full avatar with fallback", () => {
    render(
      <Avatar>
        <AvatarImage src="/avatar.png" alt="John Doe" />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    // In jsdom, image never loads so fallback is shown
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  it("forwards additional props to Avatar", () => {
    render(<Avatar data-testid="user-avatar" />);
    expect(screen.getByTestId("user-avatar")).toBeInTheDocument();
  });

  it("supports different sizes via className", () => {
    const { rerender, container } = render(<Avatar className="h-8 w-8" />);
    expect(container.firstChild).toHaveClass("h-8");
    expect(container.firstChild).toHaveClass("w-8");

    rerender(<Avatar className="h-16 w-16" />);
    expect(container.firstChild).toHaveClass("h-16");
    expect(container.firstChild).toHaveClass("w-16");
  });
});
