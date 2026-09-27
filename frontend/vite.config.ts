import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: {
      '/auth': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/papers/upload': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/papers/search-history': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/api': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/papers': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/ai': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/ops': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      // Proxy specific /research API endpoints to backend
      // Allow /research frontend route to render while API calls go to backend
      '/research/workspaces': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/questions': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/artifacts': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/intelligence': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/gap': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/evidence': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/opportunity': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      '/research/paper-check': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
      // Proxy workspaces API calls but allow frontend route to render
      // The frontend uses /workspaces/ (with trailing slash) for API calls
      // and /workspaces (without trailing slash) for navigation
      '/workspaces/': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 2000,
  },
})
