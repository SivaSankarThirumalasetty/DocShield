import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const devApiTarget =
    env.VITE_DEV_PROXY_TARGET ||
    env.VITE_API_BASE_URL ||
    "http://127.0.0.1:8000";

  return {
    base: "/",
    plugins: [react()],
    build: {
      outDir: "dist",
      assetsDir: "assets",
      sourcemap: false,
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: devApiTarget,
          changeOrigin: true,
        },
        "/health": {
          target: devApiTarget,
          changeOrigin: true,
        },
        "/ready": {
          target: devApiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
