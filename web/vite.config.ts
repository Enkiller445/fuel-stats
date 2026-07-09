import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// base = /fuel-stats/ — сайт живёт на https://enkiller445.github.io/fuel-stats/
export default defineConfig({
  base: "/fuel-stats/",
  plugins: [react()],
})
