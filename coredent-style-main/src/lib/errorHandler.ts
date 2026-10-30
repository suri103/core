import { logger } from "./logger";

export function setupGlobalErrorHandlers() {
  if (typeof window !== "undefined") {
    window.onerror = function (message, source, lineno, colno, error) {
      logger.error("Global window error", error || new Error(String(message)), {
        source,
        lineno,
        colno,
      });
      return false;
    };

    window.onunhandledrejection = function (event) {
      logger.error("Unhandled promise rejection", event.reason instanceof Error ? event.reason : new Error(String(event.reason)));
    };
  }
}
