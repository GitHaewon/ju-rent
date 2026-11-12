import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'JU_RENT_')
  return {
    plugins: [react()],
    server: { proxy: { '/api': env.JU_RENT_API_TARGET || 'http://127.0.0.1:8000' } },
    test: { environment: 'node' },
  }
})
