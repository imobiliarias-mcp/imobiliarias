import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { App } from "./App";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root not found");
}

registerImageCache();

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

/** Service workers need a secure context: HTTPS in production, or localhost during development. */
function registerImageCache(): void {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    return;
  }
  navigator.serviceWorker.register("/sw.js").catch(() => {
    // Without the worker the photos still load from the network.
  });
}
