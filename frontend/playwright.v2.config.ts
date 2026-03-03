import { createAppPlaywrightConfig } from './playwright.shared'

export default createAppPlaywrightConfig({
  testMatch: ['v2/*.spec.ts'],
  outputDir: './test-results/v2',
  baseURL: 'http://127.0.0.1:4174',
  viewport: { width: 1280, height: 800 },
  webServerCommand: 'npm run dev:teacher -- --host 127.0.0.1 --port 4174',
  webServerUrl: 'http://127.0.0.1:4174',
})
