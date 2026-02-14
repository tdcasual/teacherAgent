import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const configDir = path.dirname(fileURLToPath(import.meta.url))

type AppPlaywrightConfigOptions = {
  testMatch?: string[]
  testIgnore?: string[]
  outputDir: string
  baseURL: string
  viewport: { width: number; height: number }
  webServerCommand: string
  webServerUrl: string
}

export function createAppPlaywrightConfig({
  testMatch,
  testIgnore,
  outputDir,
  baseURL,
  viewport,
  webServerCommand,
  webServerUrl,
}: AppPlaywrightConfigOptions) {
  return defineConfig({
    testDir: './e2e',
    ...(testMatch ? { testMatch } : {}),
    ...(testIgnore ? { testIgnore } : {}),
    timeout: 60_000,
    expect: {
      timeout: 8_000,
    },
    fullyParallel: false,
    retries: 0,
    reporter: 'list',
    outputDir,
    use: {
      baseURL,
      headless: true,
      viewport,
      screenshot: 'only-on-failure',
      trace: 'retain-on-failure',
      video: 'retain-on-failure',
    },
    webServer: {
      command: webServerCommand,
      cwd: configDir,
      url: webServerUrl,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  })
}
