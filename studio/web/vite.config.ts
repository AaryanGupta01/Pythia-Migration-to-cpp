import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', chunkSizeWarningLimit: 8000, sourcemap: false },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.PYTHIA_API ?? 'http://127.0.0.1:8765', ws: true, changeOrigin: true },
    },
  },
})
