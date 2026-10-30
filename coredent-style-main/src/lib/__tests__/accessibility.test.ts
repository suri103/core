import { describe, it, expect, vi, afterEach } from "vitest";
import { setupSkipLink } from "../accessibility";

describe("accessibility", () => {
  let cleanup: (() => void) | undefined;

  afterEach(() => {
    if (cleanup) {
      cleanup();
      cleanup = undefined;
    }
    document.body.innerHTML = "";
  });

  it("returns a cleanup function in the browser", () => {
    cleanup = setupSkipLink();
    expect(typeof cleanup).toBe("function");
  });

  it("focuses the main-content element on Alt+Tab", () => {
    cleanup = setupSkipLink();
    const main = document.createElement("div");
    main.id = "main-content";
    main.tabIndex = -1;
    document.body.appendChild(main);
    const focusSpy = vi.spyOn(main, "focus");

    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      altKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(event);

    expect(focusSpy).toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(true);
  });

  it("does nothing when Alt is not held", () => {
    cleanup = setupSkipLink();
    const main = document.createElement("div");
    main.id = "main-content";
    main.tabIndex = -1;
    document.body.appendChild(main);
    const focusSpy = vi.spyOn(main, "focus");

    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      altKey: false,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(event);

    expect(focusSpy).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("does nothing when main-content element is absent", () => {
    cleanup = setupSkipLink();
    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      altKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });

  it("removes the listener when the returned cleanup runs", () => {
    cleanup = setupSkipLink();
    const main = document.createElement("div");
    main.id = "main-content";
    main.tabIndex = -1;
    document.body.appendChild(main);
    const focusSpy = vi.spyOn(main, "focus");

    cleanup!();
    cleanup = undefined;

    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      altKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(event);

    expect(focusSpy).not.toHaveBeenCalled();
  });
});
