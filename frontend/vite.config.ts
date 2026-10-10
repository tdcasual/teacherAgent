import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        inlineWorkboxRuntime: true,
      },
      includeAssets: ['icon.svg'],
      manifest: {
        name: '教学工作流',
        short_name: '作业助手',
        description: '单校作业产品',
        theme_color: '#0b3d91',
        background_color: '#f7f7f7',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml' }
        ]
      }
    })
  ],
  server: {
    port: 5173
  }
})
