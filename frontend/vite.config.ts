import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Em desenvolvimento, o Vite serve o React em :5173 e faz proxy de /api/*
// para o FastAPI em :8000 — assim o navegador pensa que tudo é a mesma origem
// e o cookie httpOnly funciona sem gambiarra de CORS.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
