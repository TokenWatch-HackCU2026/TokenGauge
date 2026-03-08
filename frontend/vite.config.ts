import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/usage": "http://api:3001",
      "/dashboard": "http://api:3001",
      "/api": "http://api:3001",
      "/health": "http://api:3001",
    },
  },
});
