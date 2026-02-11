import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

export default defineConfig({
  root: 'apps/teacher',
  publicDir: '../../public',
  plugins: [
    tailwindcss(),
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: '物理教学助手（老师端）',
        short_name: '物理老师端',
        description: '物理教学助手老师端控制台',
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
      '@teacher': resolve(__dirname, 'apps/teacher/src'),
    },
  },
  build: {
    outDir: '../../dist-teacher',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) {
            return 'vendor-react'
          }
          if (
            id.includes('/remark-') ||
            id.includes('/rehype-') ||
            id.includes('/unified/') ||
            id.includes('/unist-util-visit/') ||
            id.includes('/katex/')
          ) {
            return 'vendor-markdown'
          }
          return undefined
        },
      },
    },
  },
  server: {
    port: 3002,
  },
})
