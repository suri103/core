import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NavLink } from "../NavLink";

const renderInRouter = (ui: React.ReactNode, initialPath = "/") => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>{ui}</MemoryRouter>,
  );
};

describe("NavLink", () => {
  it("renders an anchor pointing to the target path", () => {
    renderInRouter(
      <NavLink to="/dashboard" data-testid="nav">
        Dashboard
      </NavLink>,
    );
    const link = screen.getByTestId("nav");
    expect(link.tagName).toBe("A");
    expect(link.getAttribute("href")).toBe("/dashboard");
    expect(link.textContent).toBe("Dashboard");
  });

  it("applies the active class when the current route matches", () => {
    renderInRouter(
      <NavLink to="/" activeClassName="active" data-testid="nav">
        Home
      </NavLink>,
      "/",
    );
    const link = screen.getByTestId("nav");
    expect(link.className).toContain("active");
  });
});
