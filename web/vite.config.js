import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // VITE_API_PORT overrides the backend port when 8000 is taken by something else.
  const env = loadEnv(mode, process.cwd(), "");
  const apiPort = env.VITE_API_PORT || 8000;
  // VITE_BASE lets the static build be served from a subpath (GitHub Pages).
  const base = env.VITE_BASE || "/";

  return {
    base,
    plugins: [react()],
    server: {
      host: true,
      proxy: {
        // Forward API calls to the FastAPI backend (uvicorn server:app).
        "/api": { target: `http://localhost:${apiPort}`, changeOrigin: true },
      },
    },
  };
});
