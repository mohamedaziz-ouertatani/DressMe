import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8000 (backend/). In development every /api/... call is
// forwarded there, so the browser only ever talks to one origin.
// DRESSME_API=http://127.0.0.1:8001 points it at another API (e.g. a second copy for a check).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.DRESSME_API ?? 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
