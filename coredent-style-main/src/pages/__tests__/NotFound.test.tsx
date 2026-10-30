import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import NotFound from "../NotFound";

describe("NotFound Page", () => {
  it("renders 404 heading and message", () => {
    render(
      <BrowserRouter>
        <NotFound />
      </BrowserRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("404");
    expect(screen.getByText(/page not found/i)).toBeInTheDocument();
  });

  it("has a link back to home", () => {
    render(
      <BrowserRouter>
        <NotFound />
      </BrowserRouter>,
    );
    const homeLink = screen.getByRole("link", { name: /return to home/i });
    expect(homeLink).toHaveAttribute("href", "/");
  });
});
