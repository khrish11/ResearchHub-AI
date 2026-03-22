import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('firebase')) {
            return 'vendor-firebase'
          }
          if (id.includes('react-dom') || id.includes('react')) {
            return 'vendor-react'
          }
          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }
          return 'vendor-core'
        },
      },
    },
  },
})
