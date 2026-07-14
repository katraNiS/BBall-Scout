import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" ώστε το build να δουλεύει με file:// origin μέσα στο Electron.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    host: "127.0.0.1", // bind IPv4 ρητά — αλλιώς Vite ακούει μόνο σε ::1 (IPv6)
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
