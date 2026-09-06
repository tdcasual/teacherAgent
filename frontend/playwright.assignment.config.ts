import { createAppPlaywrightConfig } from './playwright.shared'

export default createAppPlaywrightConfig({
  testMatch: ['assignment-core-loop.spec.ts'],
  outputDir: './test-results/assignment',
  baseURL: 'http://127.0.0.1:4274',
  viewport: { width: 1280, height: 800 },
  webServerCommand: 'npm run dev:teacher -- --host 127.0.0.1 --port 4274 --force',
  webServerUrl: 'http://127.0.0.1:4274',
  extraWebServers: [
    {
      command: 'npm run dev:student -- --host 127.0.0.1 --port 4275 --force',
      url: 'http://127.0.0.1:4275',
    },
  ],
})
