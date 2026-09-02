import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  define: {
    global: 'globalThis',
  },
  resolve: {
    alias: {
      './rng': 'uuid/dist/esm-browser/rng.js',
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/invocations': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
