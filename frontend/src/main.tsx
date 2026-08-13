import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/source-sans-3";
import "@fontsource-variable/space-grotesk";
import App from "./App";
import { initializeTheme } from "./useTheme";

const rootElement = document.getElementById("root");

if (rootElement === null) {
  throw new Error("Missing #root element");
}

initializeTheme();

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
