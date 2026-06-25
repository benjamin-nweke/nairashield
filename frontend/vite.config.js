import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  server: {
    proxy: {
      '/predict': 'http://localhost:5000',
      '/api': 'http://localhost:5000',
      '/health': 'http://localhost:5000',
    }
  }
})
