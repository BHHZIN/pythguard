import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000,
    // Proxy API calls to the Python backend during local development.
    // This avoids CORS issues when running frontend on :3000 and backend on :8000.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "dist",
    // Raise the chunk size warning limit — wallet adapter libraries are large
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Split large vendor chunks for better caching
        manualChunks: {
          "solana-wallet": [
            "@solana/wallet-adapter-react",
            "@solana/wallet-adapter-react-ui",
            "@solana/wallet-adapter-phantom",
            "@solana/web3.js",
          ],
          "charting": ["lightweight-charts"],
          "vendor": ["react", "react-dom", "axios"],
        },
      },
    },
  },
});
