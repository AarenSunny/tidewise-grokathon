import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
    css: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/query": "http://localhost:8000",
      "/recommend": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/spots": "http://localhost:8000",
      "/debug": "http://localhost:8000",
    },
  },
});
