import { createAppPlaywrightConfig } from './playwright.shared'

export default createAppPlaywrightConfig({
  testMatch: ['assignment-core-loop.spec.ts'],
  outputDir: './test-results/assignment',
  baseURL: 'http://127.0.0.1:4174',
  viewport: { width: 1280, height: 800 },
  webServerCommand: 'npm run dev:teacher -- --host 127.0.0.1 --port 4174 --force',
  webServerUrl: 'http://127.0.0.1:4174',
  extraWebServers: [
    {
      command: 'npm run dev:student -- --host 127.0.0.1 --port 4175',
      url: 'http://127.0.0.1:4175',
    },
  ],
})
