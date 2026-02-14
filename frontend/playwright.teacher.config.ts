import { createAppPlaywrightConfig } from './playwright.shared'

export default createAppPlaywrightConfig({
  testIgnore: ['**/student-*.spec.ts'],
  outputDir: './test-results/teacher',
  baseURL: 'http://127.0.0.1:4174',
  viewport: { width: 1280, height: 800 },
  webServerCommand: 'npm run dev:teacher -- --host 127.0.0.1 --port 4174',
  webServerUrl: 'http://127.0.0.1:4174',
})
