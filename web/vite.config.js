import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // VITE_API_PORT overrides the backend port when 8000 is taken by something else.
  const env = loadEnv(mode, process.cwd(), "");
  const apiPort = env.VITE_API_PORT || 8000;

  return {
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
