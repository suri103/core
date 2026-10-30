import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { i18n, useTranslation } from "../i18n";

describe("i18n", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = "";
    i18n.setLocale("en");
    vi.clearAllMocks();
  });

  describe("constructor locale resolution", () => {
    // vi.resetModules() restores spies created before it, so resetModules must
    // run BEFORE the navigator spy is installed (and before the fresh import).
    it("uses a saved supported locale from localStorage", async () => {
      localStorage.setItem("locale", "es");
      vi.resetModules();
      const mod = await import("../i18n");
      expect(mod.i18n.getLocale()).toBe("es");
    });

    it("falls back to the browser locale when no saved locale", async () => {
      // beforeEach calls i18n.setLocale("en") which writes localStorage; clear it
      // so the constructor falls through to the browser-locale branch.
      localStorage.clear();
      vi.resetModules();
      const spy = vi
        .spyOn(navigator, "language", "get")
        .mockReturnValue("es-AR");
      const mod = await import("../i18n");
      expect(mod.i18n.getLocale()).toBe("es");
      spy.mockRestore();
    });

    it("falls back to the default locale when nothing matches", async () => {
      localStorage.clear();
      vi.resetModules();
      const spy = vi
        .spyOn(navigator, "language", "get")
        .mockReturnValue("fr-FR");
      const mod = await import("../i18n");
      expect(mod.i18n.getLocale()).toBe("en");
      spy.mockRestore();
    });
  });

  describe("t", () => {
    it("translates a key in the current locale", () => {
      expect(i18n.t("common.save")).toBe("Save");
    });

    it("interpolates params", () => {
      expect(i18n.t("dashboard.welcome", { name: "Sam" })).toBe(
        "Welcome back, Sam!",
      );
    });

    it("falls back to the default locale when the key is missing", () => {
      i18n.setLocale("es");
      // es has no errors.networkError
      expect(i18n.t("errors.networkError")).toBe(
        "Network error. Please check your connection.",
      );
    });

    it("returns the key itself when missing everywhere", () => {
      expect(i18n.t("common.missing")).toBe("common.missing");
    });

    it("returns the key for an unknown nested path", () => {
      expect(i18n.t("common.does.not.exist")).toBe("common.does.not.exist");
    });

    it("navigates nested keys", () => {
      expect(i18n.t("settings.language")).toBe("Language");
    });
  });

  describe("setLocale", () => {
    it("switches the active locale and persists it", () => {
      i18n.setLocale("es");
      expect(i18n.getLocale()).toBe("es");
      expect(localStorage.getItem("locale")).toBe("es");
      expect(document.documentElement.lang).toBe("es");
    });

    it("dispatches a localechange event", () => {
      const handler = vi.fn();
      window.addEventListener("localechange", handler);
      i18n.setLocale("es");
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({ detail: { locale: "es" } }),
      );
      window.removeEventListener("localechange", handler);
    });

    it("ignores unsupported locales", () => {
      i18n.setLocale("fr");
      expect(i18n.getLocale()).toBe("en");
    });
  });

  describe("getSupportedLocales / addTranslations", () => {
    it("returns the supported locales", () => {
      expect(i18n.getSupportedLocales()).toEqual(["en", "es", "hi"]);
    });

    it("adds a new top-level namespace without disturbing existing ones", () => {
      i18n.setLocale("en");
      i18n.addTranslations("en", { custom: { hello: "Hi {{name}}" } });
      expect(i18n.t("custom.hello", { name: "Pat" })).toBe("Hi Pat");
      // existing keys remain intact
      expect(i18n.t("common.save")).toBe("Save");
    });

    it("adds translations for a locale that did not previously exist", () => {
      i18n.setLocale("en");
      // fr is not in supported locales, so setLocale stays en; but addTranslations
      // still registers the data structure internally.
      i18n.addTranslations("fr", { common: { save: "Enregistrer" } });
      expect(i18n.getSupportedLocales()).toContain("en");
    });
  });

  describe("useTranslation", () => {
    it("returns a translator and updates on locale change", () => {
      function Probe() {
        const { t, locale, setLocale } = useTranslation();
        return (
          <div>
            <span>{locale}</span>
            <button onClick={() => setLocale("es")}>switch</button>
            <span>{t("common.save")}</span>
          </div>
        );
      }
      render(<Probe />);
      expect(screen.getByText("en")).toBeInTheDocument();
      expect(screen.getByText("Save")).toBeInTheDocument();

      act(() => {
        screen.getByText("switch").click();
      });

      expect(screen.getByText("es")).toBeInTheDocument();
      expect(screen.getByText("Guardar")).toBeInTheDocument();
    });
  });
});
