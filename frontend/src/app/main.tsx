import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Router } from "./router.tsx";

window.addEventListener("vite:preloadError", () => window.location.reload());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Router />
  </StrictMode>,
);
