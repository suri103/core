import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Index from "../Index";

describe("Index page", () => {
  it("renders the welcome heading", () => {
    render(<Index />);
    expect(screen.getByText(/Welcome to Your Blank App/)).toBeInTheDocument();
  });
});
