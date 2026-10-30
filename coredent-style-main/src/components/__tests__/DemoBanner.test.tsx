import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DemoBanner } from "../DemoBanner";

describe("DemoBanner", () => {
  it("renders the demo mode banner in non-production", () => {
    // The test environment is development (Vite test mode), so the banner
    // is rendered.
    render(<DemoBanner />);
    expect(screen.getByText(/Demo Mode/)).toBeInTheDocument();
  });
});
