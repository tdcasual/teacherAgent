import { createAppPlaywrightConfig } from './playwright.shared'

export default createAppPlaywrightConfig({
  testMatch: ['student-*.spec.ts', 'storage-resilience.spec.ts', 'security-markdown-sanitize.spec.ts'],
  outputDir: './test-results/student',
  baseURL: 'http://127.0.0.1:4175',
  viewport: { width: 390, height: 844 },
  webServerCommand: 'npm run dev:student -- --host 127.0.0.1 --port 4175',
  webServerUrl: 'http://127.0.0.1:4175',
})
