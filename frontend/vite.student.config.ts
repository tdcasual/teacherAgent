import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

export default defineConfig({
  root: 'apps/student',
  publicDir: '../../public',
  plugins: [
    tailwindcss(),
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: '物理学习助手（学生端）',
        short_name: '物理学生端',
        description: '物理学习助手学生端控制台',
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
