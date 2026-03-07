import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/usage": "http://localhost:8000",
      "/keys": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
