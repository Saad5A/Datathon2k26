import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import fs from 'node:fs'

// No dev proxy: the browser calls VITE_API_URL directly, exactly as in production,
// so the backend's CORS allow-list is exercised during development too.
export default defineConfig({
  base: '/',
  plugins: [react(), {
    name: 'pancakess-evolution-route',
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        const pathname = (req.url || '').split('?')[0]
        if (pathname === '/evolve') req.url = (req.url || '').replace('/evolve', '/evolution/index.html')
        else if (pathname.startsWith('/evolve/')) req.url = (req.url || '').replace('/evolve/', '/evolution/')
        next()
      })
    },
    closeBundle() {
      const source = path.resolve(__dirname, 'evolution')
      const destination = path.resolve(__dirname, 'dist/evolve')
      fs.rmSync(destination, { recursive: true, force: true })
      fs.cpSync(source, destination, { recursive: true })
    },
  }],
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
