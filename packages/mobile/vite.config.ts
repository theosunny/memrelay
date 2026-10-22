import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { port: 1421, strictPort: true, host: "127.0.0.1" },
  preview: { port: 1421, strictPort: true, host: "127.0.0.1" },
  build: { target: "es2022" },
});
