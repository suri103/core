import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { setupGlobalErrorHandlers } from "./lib/errorHandler";
import { setupSkipLink } from "./lib/accessibility";
import { initWebVitals } from "./lib/webVitals";
import { logger } from "./lib/logger";

// Setup global error handlers
setupGlobalErrorHandlers();

// Setup accessibility features
setupSkipLink();

// Initialize Web Vitals monitoring
initWebVitals();

// Enable MSW in development mode
async function enableMocking() {
  if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO_MODE === 'true') {
    const { worker } = await import('./test/mocks/browser');
    return worker.start({
      onUnhandledRequest: 'bypass',
    });
  }
}

function renderApp() {
  const rootElement = document.getElementById("root");
  if (!rootElement) {
    throw new Error("CoreDent root element was not found");
  }
  createRoot(rootElement).render(<App />);
}

enableMocking()
  .then(renderApp)
  .catch((error: unknown) => {
    // A failed development mock bootstrap must not leave production/dev users
    // staring at a blank page; render against the real API instead.
    logger.error("Mock service worker startup failed", error instanceof Error ? error : new Error(String(error)));
    renderApp();
  });
