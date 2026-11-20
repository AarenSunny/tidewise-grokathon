import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/query': 'http://localhost:8000',
      '/recommend': 'http://localhost:8000',
      '/score': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/spots': 'http://localhost:8000',
      '/debug': 'http://localhost:8000',
    },
  },
});
