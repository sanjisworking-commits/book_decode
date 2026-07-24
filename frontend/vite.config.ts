import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Prefer VITE_API_PROXY_TARGET; default 8003 (common when 8000 is taken).
  const apiTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8003";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/books": apiTarget,
        "/demo": apiTarget,
        "/health": apiTarget,
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./tests/setup.ts"],
    },
  };
});
