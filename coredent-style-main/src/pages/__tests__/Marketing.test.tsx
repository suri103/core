import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Marketing from "../Marketing";

describe("Marketing Page", () => {
  it("renders the page heading and a 'Not available' badge", () => {
    render(
      <BrowserRouter>
        <Marketing />
      </BrowserRouter>,
    );
    expect(
      screen.getByRole("heading", { level: 1, name: /marketing/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not available/i)).toBeInTheDocument();
  });

  it("honestly states that marketing is not implemented", () => {
    render(
      <BrowserRouter>
        <Marketing />
      </BrowserRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /marketing is not implemented/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no campaign, subscriber, patient-segment, engagement, or revenue data is available/i),
    ).toBeInTheDocument();
  });

  it("lists planned areas as unavailable rather than showing fabricated data", () => {
    render(
      <BrowserRouter>
        <Marketing />
      </BrowserRouter>,
    );
    // Planned areas are enumerated as coming features, without fabricated stats.
    for (const name of ["Campaigns", "Patient segments", "Templates", "Analytics"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    // The old fabricated UI is gone.
    expect(screen.queryByRole("button", { name: /new campaign/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/spring cleaning special/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/new patient welcome/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /campaigns/i })).not.toBeInTheDocument();
  });
});
