import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/analyze': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/inbox': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
