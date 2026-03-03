import { expect, test, type Page } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

const readLayout = async (page: Page) =>
  page.evaluate(() => {
    const shell = document.querySelector('.chat-shell') as HTMLElement | null
    const messages = document.querySelector('.messages') as HTMLElement | null
    const composer = document.querySelector('form') as HTMLElement | null
    if (!shell || !messages || !composer) return null
    const shellRect = shell.getBoundingClientRect()
    const messagesRect = messages.getBoundingClientRect()
    const composerRect = composer.getBoundingClientRect()
    return {
      shellScrollTop: shell.scrollTop,
      messagesTopOffset: messagesRect.top - shellRect.top,
      composerBottomGap: window.innerHeight - composerRect.bottom,
    }
  })

const expectAnchored = async (page: Page, baseline: { messagesTopOffset: number; composerBottomGap: number }) => {
  await expect.poll(async () => (await readLayout(page))?.shellScrollTop ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(1)
  await expect
    .poll(async () => Math.abs(((await readLayout(page))?.messagesTopOffset ?? Number.POSITIVE_INFINITY) - baseline.messagesTopOffset))
    .toBeLessThanOrEqual(2)
  await expect
    .poll(async () => Math.abs(((await readLayout(page))?.composerBottomGap ?? Number.POSITIVE_INFINITY) - baseline.composerBottomGap))
    .toBeLessThanOrEqual(2)
}

test('teacher: switching sessions keeps chat shell anchored', async ({ page }) => {
  await page.setViewportSize({ width: 1292, height: 1169 })
  const longHistory = Array.from({ length: 36 }, (_, i) => ({
    ts: new Date(Date.now() - (36 - i) * 60_000).toISOString(),
    role: i % 2 === 0 ? 'assistant' : 'user',
    content: `MAIN-LONG-${i} ` + '内容'.repeat(48),
  }))
  const shortHistory = [{ ts: new Date().toISOString(), role: 'assistant', content: 'S2-SHORT-0' }]

  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
      teacherSkillsOpen: 'false',
    },
    apiMocks: {
      historyBySession: {
        main: longHistory,
        s2: shortHistory,
      },
    },
  })

  await expect(page.locator('.message .text').filter({ hasText: 'MAIN-LONG-0' }).first()).toBeVisible()
  const baseline = await readLayout(page)
  expect(baseline).not.toBeNull()

  const s2Session = page.locator('.session-item', { hasText: 's2' }).locator('.session-select').first()
  const mainSession = page.locator('.session-item', { hasText: 'main' }).locator('.session-select').first()

  await s2Session.click()
  await expect(page.locator('.message .text').filter({ hasText: 'S2-SHORT-0' }).first()).toBeVisible()
  await expectAnchored(page, baseline!)

  await mainSession.click()
  await expect(page.locator('.message .text').filter({ hasText: 'MAIN-LONG-0' }).first()).toBeVisible()
  await expectAnchored(page, baseline!)
})
