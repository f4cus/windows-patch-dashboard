import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function normalizeBasePath(value) {
  if (!value) {
    return "/";
  }
  const leadingSlash = value.startsWith("/") ? value : `/${value}`;
  return leadingSlash.endsWith("/") ? leadingSlash : `${leadingSlash}/`;
}

export default defineConfig({
  base: normalizeBasePath(process.env.PAGES_BASE_PATH),
  plugins: [react()],
});
