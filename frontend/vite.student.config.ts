import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

export default defineConfig({
  root: 'apps/student',
  publicDir: '../../public',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Physics Learning Helper (Student)',
        short_name: 'PhysicsStudent',
        description: 'Student console for physics helper',
        theme_color: '#2f6d6b',
        background_color: '#f6f2ea',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml' }],
      },
    }),
  ],
  resolve: {
    alias: {
      '@student': resolve(__dirname, 'apps/student/src'),
    },
  },
  build: {
    outDir: '../../dist-student',
    emptyOutDir: true,
  },
  server: {
    port: 3001,
  },
})
