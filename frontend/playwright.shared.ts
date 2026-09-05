import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const configDir = path.dirname(fileURLToPath(import.meta.url))

type ExtraWebServer = {
  command: string
  url: string
}

type AppPlaywrightConfigOptions = {
  testMatch?: string[]
  testIgnore?: string[]
  outputDir: string
  baseURL: string
  viewport: { width: number; height: number }
  webServerCommand: string
  webServerUrl: string
  extraWebServers?: ExtraWebServer[]
}

const webServerOptions = {
  cwd: configDir,
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
}

export function createAppPlaywrightConfig({
  testMatch,
  testIgnore,
  outputDir,
  baseURL,
  viewport,
  webServerCommand,
  webServerUrl,
  extraWebServers,
}: AppPlaywrightConfigOptions) {
  const primaryServer = {
    command: webServerCommand,
    url: webServerUrl,
    ...webServerOptions,
  }
  const webServer =
    extraWebServers && extraWebServers.length > 0
      ? [primaryServer, ...extraWebServers.map((server) => ({ ...server, ...webServerOptions }))]
      : primaryServer

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
    webServer,
  })
}
