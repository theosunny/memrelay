import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const here = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: "127.0.0.1",
    fs: { allow: [here, fileURLToPath(new URL("../website", import.meta.url))] },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: { target: "es2022" },
});
