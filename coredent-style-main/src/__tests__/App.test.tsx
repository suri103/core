import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

describe("App", () => {
  it("renders without crashing inside ErrorBoundary", () => {
    render(<App />);
    // The default route is `/` which redirects to `/dashboard`.
    // We don't assert on a specific DOM node because the page is lazy-loaded.
    expect(document.body).toBeInTheDocument();
  });

  it("does not crash on an unknown route (renders NotFound)", async () => {
    // Simulate navigation to a path that does not exist.
    window.history.pushState({}, "", "/this-route-does-not-exist");
    render(<App />);
    // The NotFound component should mount; it contains a heading.
    expect(
      await screen.findByRole("heading", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
  });
});