import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The backend (FastAPI, `uv run loupe api`) listens on :8000 and serves everything under /api.
const BACKEND = process.env.LOUPE_BACKEND ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    // plotly.js is ~4.5 MB minified; it lives in its own lazily loaded chunk.
    chunkSizeWarningLimit: 5000,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
