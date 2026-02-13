import { expect, test, type Page } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

const buildRoutingOverview = (channelCount: number) => {
  const channels = Array.from({ length: channelCount }, (_, index) => {
    const channelId = `channel_${String(index + 1).padStart(2, '0')}`
    return {
      channel_id: channelId,
      name: `通道 ${index + 1}`,
      enabled: true,
      capabilities: ['chat'],
      base_weight: 1,
      dynamic_weight: 1,
      health_score: 1,
      latency_ms: 120,
      rpm_limit: 120,
      tpm_limit: 120000,
      queue_depth: 0,
      warm: true,
      tags: ['default'],
      meta: {
        provider: index % 2 === 0 ? 'openai' : 'deepseek',
        model: index % 2 === 0 ? 'gpt-4.1-mini' : 'deepseek-chat',
      },
    }
  })

  return {
    ok: true,
    teacher_id: 'T001',
    routing: {
      channels,
      defaults: {
        strategy: 'weighted',
        fallback_channel_id: channels[0]?.channel_id || null,
      },
      rules: [],
      diagnostics: {
        updated_at: new Date().toISOString(),
      },
    },
  }
}

const setupRoutingMocks = async (page: Page, channelCount: number) => {
  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRoutingOverview(channelCount)),
    })
  })
  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        teacher_id: 'T001',
        providers: [],
        shared_catalog: {
          providers: [
            {
              provider: 'openai',
              source: 'env',
              modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
            },
          ],
          defaults: { provider: 'openai', mode: 'openai-chat' },
          fallback_chain: ['openai'],
        },
        catalog: {
          providers: [
            {
              provider: 'openai',
              source: 'env',
              modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
            },
          ],
          defaults: { provider: 'openai', mode: 'openai-chat' },
          fallback_chain: ['openai'],
        },
        config_path: '/tmp/provider-registry.json',
      }),
    })
  })
}

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

test('teacher: exiting routing view should not leak chat-shell scroll offset', async ({ page }) => {
  await page.setViewportSize({ width: 1292, height: 1169 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
      teacherSkillsOpen: 'false',
    },
  })
  await setupRoutingMocks(page, 80)

  const baseline = await readLayout(page)
  expect(baseline).not.toBeNull()

  await page.getByRole('button', { name: '模型路由', exact: true }).click()
  await expect(page.locator('.routing-page')).toBeVisible()

  const shell = page.locator('.chat-shell')
  await shell.evaluate((el) => {
    el.scrollTop = Math.max(0, Math.floor(el.scrollHeight * 0.6))
  })

  await page.getByLabel('设置').click()
  await expect(page.getByRole('dialog', { name: '设置' })).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await expect(page.locator('.routing-page')).toBeHidden()
  await expect(page.getByPlaceholder('输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行')).toBeVisible()

  await expectAnchored(page, baseline!)
})
