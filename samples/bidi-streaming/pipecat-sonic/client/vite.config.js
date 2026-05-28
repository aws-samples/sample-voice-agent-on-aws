import { defineConfig } from "vite";

export default defineConfig({
  // Use relative paths so built assets work behind any proxy prefix
  base: "./",
  optimizeDeps: {
    include: ["protobufjs/minimal"],
  },
  server: {
    port: 3000,
    open: true,
    allowedHosts: [".cloudfront.net"],
    proxy: {
      "/start": {
        target: "http://localhost:8081",
        changeOrigin: true,
      },
    },
  },
});
