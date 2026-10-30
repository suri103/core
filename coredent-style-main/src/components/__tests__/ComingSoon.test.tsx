import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComingSoon } from "../ComingSoon";

describe("ComingSoon", () => {
  it("renders the page name", () => {
    render(<ComingSoon pageName="Reports" />);
    expect(screen.getByText("Reports")).toBeInTheDocument();
  });

  it("renders a custom description when provided", () => {
    render(
      <ComingSoon pageName="Reports" description="Custom desc" />,
    );
    expect(screen.getByText("Custom desc")).toBeInTheDocument();
  });

  it("renders the default description when none is provided", () => {
    render(<ComingSoon pageName="Billing" />);
    expect(
      screen.getByText(/This feature is coming soon/),
    ).toBeInTheDocument();
  });

  it("renders the in-development badge", () => {
    render(<ComingSoon pageName="Anything" />);
    expect(screen.getByText(/In Development/)).toBeInTheDocument();
  });
});
