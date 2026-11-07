import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// `/predict` is proxied to the Python model server during development.
// Override the target with PREDICT_PROXY_TARGET=http://host:port npm run dev
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
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
    server: {
      proxy: {
        '/predict': {
          target: env.PREDICT_PROXY_TARGET ?? 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
