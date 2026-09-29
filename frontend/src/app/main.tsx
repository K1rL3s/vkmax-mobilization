import { StrictMode } from "react";
import { focusManager } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { Router } from "./router.tsx";

window.addEventListener("vite:preloadError", () => window.location.reload());

focusManager.setEventListener((onFocus) => {
  const listener = () => onFocus();
  window.addEventListener("visibilitychange", listener);
  window.addEventListener("focus", listener);

  return () => {
    window.removeEventListener("visibilitychange", listener);
    window.removeEventListener("focus", listener);
  };
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Router />
  </StrictMode>,
);
