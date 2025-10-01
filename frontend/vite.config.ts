import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'https://spotify-app-backend-yqzt.onrender.com',
        changeOrigin: true,
        secure: false,
      },
      '/callback': {
        target: 'https://spotify-app-backend-yqzt.onrender.com',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  build: {
    // Ensure CSP allows backend connections
    rollupOptions: {
      external: [],
    }
  }
})

