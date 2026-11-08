import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// The browser calls VITE_API_URL directly; no dev proxy is used.
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts'],
          table: ['@tanstack/react-table', 'papaparse'],
          radix: ['@radix-ui/react-dialog', '@radix-ui/react-tooltip', '@radix-ui/react-dropdown-menu'],
        },
      },
    },
  },
})
