export function setupSkipLink() {
  if (typeof document !== "undefined") {
    // Inject key listener or skip link behavior for a11y keyboard shortcuts
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab" && e.altKey) {
        const mainContent = document.getElementById("main-content");
        if (mainContent) {
          mainContent.focus();
          e.preventDefault();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }
}
