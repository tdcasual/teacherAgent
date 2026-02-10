import { expect, test } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

const sharedCatalog = {
  providers: [
    {
      provider: 'openai',
      source: 'env',
      modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
    },
  ],
  defaults: { provider: 'openai', mode: 'openai-chat' },
  fallback_chain: ['openai'],
}

const buildRoutingOverview = (teacherId: string, channelTitle: string) => ({
  ok: true,
  teacher_id: teacherId,
  routing: {
    schema_version: 1,
    enabled: true,
    version: 1,
    updated_at: new Date().toISOString(),
    updated_by: 'e2e',
    channels: [
      {
        id: 'channel_1',
        title: channelTitle,
        target: {
          provider: 'openai',
          mode: 'openai-chat',
          model: 'gpt-4.1-mini',
        },
        params: { temperature: 0.3, max_tokens: 1024 },
        fallback_channels: [],
        capabilities: { tools: true, json: true },
      },
    ],
    rules: [],
  },
  validation: { errors: [], warnings: [] },
  history: [],
  proposals: [],
  catalog: sharedCatalog,
  config_path: '/tmp/routing.json',
})

const buildProviderOverview = (teacherId: string) => ({
  ok: true,
  teacher_id: teacherId,
  providers: [],
  shared_catalog: sharedCatalog,
  catalog: sharedCatalog,
  config_path: '/tmp/provider-registry.json',
})

const buildProviderOverviewWithPrivate = (teacherId: string) => ({
  ok: true,
  teacher_id: teacherId,
  providers: [
    {
      id: 'openai',
      provider: 'openai',
      display_name: 'OpenAI 私有覆盖',
      base_url: 'https://proxy.example.com/v1',
      api_key_masked: 'sk-***1234',
      default_mode: 'openai-chat',
      default_model: 'gpt-4.1-mini',
      enabled: true,
      source: 'private',
    },
  ],
  shared_catalog: sharedCatalog,
  catalog: sharedCatalog,
  config_path: '/tmp/provider-registry.json',
})

const setupRoutingSettingsMocks = async (page: Parameters<typeof test>[0]['page']) => {
  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const teacherId = url.searchParams.get('teacher_id') || 'teacher'
    const channelTitle = teacherId === 'teacherB' ? '渠道-B' : '渠道-A'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRoutingOverview(teacherId, channelTitle)),
    })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const teacherId = url.searchParams.get('teacher_id') || 'teacher'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverview(teacherId)),
    })
  })
}

test('settings general section exposes api base input', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByPlaceholder('http://localhost:8000').fill('http://127.0.0.1:9333')

  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('apiBaseTeacher')))
    .toBe('http://127.0.0.1:9333')
})

test('invalid saved settings section falls back to general panel', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSettingsSection: '__invalid_section__',
    },
  })
  await setupRoutingSettingsMocks(page)

  await page.getByRole('button', { name: '设置' }).click()

  await expect(page.locator('.settings-nav button.active')).toHaveText('通用')
  await expect(page.getByPlaceholder('默认 teacher')).toBeVisible()
})

test('switching teacher id discards previous local draft edits', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '渠道' }).click()

  const channelNameInput = page
    .locator('.routing-item .routing-field')
    .filter({ hasText: '名称' })
    .locator('input')
    .first()

  await expect(channelNameInput).toHaveValue('渠道-A')
  await channelNameInput.fill('本地草稿A')

  await page.getByRole('button', { name: '通用' }).click()
  page.once('dialog', async (dialog) => {
    await dialog.accept()
  })
  await page.getByPlaceholder('默认 teacher').fill('teacherB')
  await page.getByRole('button', { name: '渠道' }).click()

  await expect(channelNameInput).toHaveValue('渠道-B')
})

test('switching teacher id keeps local draft when switch is cancelled', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '渠道' }).click()

  const channelNameInput = page
    .locator('.routing-item .routing-field')
    .filter({ hasText: '名称' })
    .locator('input')
    .first()

  await channelNameInput.fill('本地草稿A')

  let dialogMessage = ''
  page.once('dialog', async (dialog) => {
    dialogMessage = dialog.message()
    await dialog.dismiss()
  })

  await page.getByRole('button', { name: '通用' }).click()
  await page.getByPlaceholder('默认 teacher').fill('teacherB')

  await expect.poll(() => dialogMessage).not.toBe('')

  await page.getByRole('button', { name: '渠道' }).click()
  await expect(channelNameInput).toHaveValue('本地草稿A')
})

test('closing settings with local draft asks for confirmation', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '渠道' }).click()

  const channelNameInput = page
    .locator('.routing-item .routing-field')
    .filter({ hasText: '名称' })
    .locator('input')
    .first()
  await channelNameInput.fill('尚未提交的草稿')

  let dialogMessage = ''
  page.once('dialog', async (dialog) => {
    dialogMessage = dialog.message()
    await dialog.dismiss()
  })

  await page.getByRole('button', { name: '关闭' }).click()

  await expect.poll(() => dialogMessage).not.toBe('')
  await expect(page.locator('.settings-overlay')).toBeVisible()
})

test('provider tab still renders when routing overview request fails', async ({ page }) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'routing overview unavailable' }),
    })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverviewWithPrivate('teacher')),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: 'Provider' }).click()

  await expect(page.getByText('OpenAI 私有覆盖')).toBeVisible()
  await expect(page.getByText('routing overview unavailable')).toBeVisible()
})

test('general tab still renders when provider overview request fails', async ({ page }) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRoutingOverview('teacher', '渠道-A')),
    })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'provider registry unavailable' }),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()

  await expect(page.getByText('线上版本：1')).toBeVisible()
  await expect(page.getByText('provider registry unavailable')).toBeVisible()
})

test('provider update sends explicit empty base_url when cleared', async ({ page }) => {
  await openTeacherApp(page)

  let lastPatchPayload: Record<string, unknown> | null = null
  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRoutingOverview('teacher', '渠道-A')),
    })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    const req = route.request()
    const method = req.method().toUpperCase()
    const pathname = new URL(req.url()).pathname

    if (method === 'GET' && pathname === '/teacher/provider-registry') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildProviderOverviewWithPrivate('teacher')),
      })
      return
    }

    if (method === 'PATCH' && pathname === '/teacher/provider-registry/providers/openai') {
      lastPatchPayload = JSON.parse(req.postData() || '{}')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, provider: { provider: 'openai' } }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: 'Provider' }).click()
  await page.locator('.provider-row summary').first().click()

  const providerRow = page.locator('.provider-row').filter({ hasText: 'OpenAI 私有覆盖' }).first()
  const baseUrlInput = providerRow.locator('.routing-field').filter({ hasText: 'Base URL' }).locator('input').first()
  await baseUrlInput.fill('')
  await providerRow.getByRole('button', { name: '保存' }).click()

  await expect.poll(() => lastPatchPayload).not.toBeNull()
  expect((lastPatchPayload || {}).base_url).toBe('')
})

test('model dropdown shows total count and full model names', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  const longModel = 'gpt-4.1-super-long-model-name-for-routing-debug-view'
  await page.route('http://localhost:8000/teacher/provider-registry/providers/openai/probe-models', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        provider_id: 'openai',
        models: ['gpt-4.1-mini', longModel, 'gpt-4.1'],
      }),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '渠道' }).click()
  await page.locator('.model-combobox-input').first().click()

  await expect(page.getByText('共 3 个模型')).toBeVisible()
  await expect(page.locator('.model-combobox-option', { hasText: longModel }).first()).toHaveAttribute('title', longModel)
})


test('single-admin save auto-applies latest routing config', async ({ page }) => {
  await openTeacherApp(page)

  let createdPayload: Record<string, any> | null = null
  let reviewedPayload: Record<string, any> | null = null
  let activeChannelTitle = '渠道-A'
  let activeVersion = 1

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const req = route.request()
    const method = req.method().toUpperCase()
    const pathname = new URL(req.url()).pathname

    if (method === 'GET' && pathname === '/teacher/llm-routing') {
      const overview = buildRoutingOverview('teacher', activeChannelTitle)
      overview.routing.version = activeVersion
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) })
      return
    }

    if (method === 'POST' && pathname === '/teacher/llm-routing/proposals') {
      createdPayload = JSON.parse(req.postData() || '{}')
      const candidate = (createdPayload?.config as Record<string, any> | undefined) || {}
      const channels = (candidate.channels as Array<Record<string, any>> | undefined) || []
      const firstTitle = String(channels[0]?.title || '').trim()
      if (firstTitle) activeChannelTitle = firstTitle
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, proposal_id: 'proposal_auto_apply_1', status: 'pending' }),
      })
      return
    }

    if (method === 'POST' && pathname === '/teacher/llm-routing/proposals/proposal_auto_apply_1/review') {
      reviewedPayload = JSON.parse(req.postData() || '{}')
      activeVersion += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, proposal_id: 'proposal_auto_apply_1', status: 'applied', version: activeVersion }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverview('teacher')),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '渠道' }).click()

  const channelNameInput = page
    .locator('.routing-item .routing-field')
    .filter({ hasText: '名称' })
    .locator('input')
    .first()

  await channelNameInput.fill('自动生效渠道')
  await page.getByRole('button', { name: '保存并生效' }).click()

  await expect.poll(() => createdPayload).not.toBeNull()
  await expect.poll(() => reviewedPayload).not.toBeNull()
  expect(Boolean(reviewedPayload?.approve)).toBe(true)

  await expect(page.getByText('配置已生效')).toBeVisible()
  await expect(channelNameInput).toHaveValue('自动生效渠道')
})


test('history tab keeps manual review and version list collapsed by default', async ({ page }) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const overview = buildRoutingOverview('teacher', '渠道-A')
    overview.proposals = [
      {
        proposal_id: 'proposal_legacy_1',
        created_at: new Date().toISOString(),
        created_by: 'teacher',
        status: 'pending',
        note: 'legacy pending review',
        validation_ok: true,
        proposal_path: '/tmp/proposal_legacy_1.json',
      },
    ]
    overview.history = [
      {
        file: '/tmp/v8.json',
        version: 8,
        saved_at: new Date().toISOString(),
        saved_by: 'teacher',
        source: 'proposal:proposal_legacy_1',
        note: 'legacy active',
      },
    ]
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverview('teacher')),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '版本历史' }).click()

  const manualReviewSection = page.locator('.routing-subsection').filter({ hasText: '待审核提案（高级）' })
  await expect(manualReviewSection.getByText('单管理员模式默认自动生效')).toBeVisible()
  await expect(manualReviewSection.getByRole('button', { name: '展开（1）' })).toBeVisible()
  await expect(manualReviewSection.getByRole('button', { name: '生效' })).toHaveCount(0)

  const historySection = page.locator('.routing-subsection').filter({ hasText: '历史版本（最近10次）' })
  await expect(historySection.getByText('默认折叠历史版本以保持界面简洁')).toBeVisible()
  await expect(historySection.getByRole('button', { name: '展开（1）' })).toBeVisible()
  await expect(historySection.getByRole('button', { name: '回滚到此版本' })).toHaveCount(0)

  await manualReviewSection.getByRole('button', { name: '展开（1）' }).click()
  await expect(manualReviewSection.getByRole('button', { name: '生效' })).toBeVisible()

  await historySection.getByRole('button', { name: '展开（1）' }).click()
  await expect(historySection.getByRole('button', { name: '回滚到此版本' })).toBeVisible()
})

test('general tab shows current active routing summary card', async ({ page }) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const overview = buildRoutingOverview('teacher', '教师主渠道')
    overview.routing.version = 3
    overview.routing.updated_at = '2026-02-10T08:00:00'
    overview.routing.rules = [
      {
        id: 'rule_teacher_primary',
        priority: 120,
        enabled: true,
        match: { roles: ['teacher'], skills: [], kinds: ['chat.agent'] },
        route: { channel_id: 'channel_1' },
      },
    ]
    overview.routing.channels[0].target.model = 'gpt-4.1-mini'
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverview('teacher')),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()

  const activeCard = page.locator('.routing-current-card')
  await expect(activeCard).toBeVisible()
  await expect(activeCard.getByText('当前生效配置')).toBeVisible()
  await expect(activeCard.getByText('rule_teacher_primary')).toBeVisible()
  await expect(activeCard.getByText('教师主渠道')).toBeVisible()
  await expect(activeCard.getByText('openai / openai-chat / gpt-4.1-mini')).toBeVisible()
})


test('history versions show readable change summary and json detail', async ({ page }) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const overview = buildRoutingOverview('teacher', '渠道-A')
    overview.history = [
      {
        file: '/tmp/v3.json',
        version: 3,
        saved_at: '2026-02-10T08:00:00',
        saved_by: 'teacher',
        source: 'proposal:proposal_3',
        note: '切换到主模型',
        summary: {
          enabled: true,
          channel_count: 2,
          rule_count: 2,
          primary_channel_id: 'channel_1',
          primary_channel_title: '渠道-A',
          primary_provider: 'openai',
          primary_mode: 'openai-chat',
          primary_model: 'gpt-4.1-mini',
          top_rule_id: 'rule_teacher_primary',
        },
        config: {
          version: 3,
          enabled: true,
          channels: [
            {
              id: 'channel_1',
              title: '渠道-A',
              target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
            },
          ],
          rules: [{ id: 'rule_teacher_primary', route: { channel_id: 'channel_1' } }],
        },
      },
      {
        file: '/tmp/v2.json',
        version: 2,
        saved_at: '2026-02-09T18:00:00',
        saved_by: 'teacher',
        source: 'proposal:proposal_2',
        note: '旧版本',
        summary: {
          enabled: true,
          channel_count: 1,
          rule_count: 1,
          primary_channel_id: 'channel_1',
          primary_channel_title: '渠道-A',
          primary_provider: 'openai',
          primary_mode: 'openai-chat',
          primary_model: 'gpt-4.1',
          top_rule_id: 'rule_teacher_v2',
        },
        config: {
          version: 2,
          enabled: true,
          channels: [
            {
              id: 'channel_1',
              title: '渠道-A',
              target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1' },
            },
          ],
          rules: [{ id: 'rule_teacher_v2', route: { channel_id: 'channel_1' } }],
        },
      },
    ] as any

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildProviderOverview('teacher')),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '版本历史' }).click()

  const historySection = page.locator('.routing-subsection').filter({ hasText: '历史版本（最近10次）' })
  await historySection.getByRole('button', { name: '展开（2）' }).click()

  await expect(historySection.getByText('变更摘要').first()).toBeVisible()
  await expect(historySection.getByText('主模型：openai / openai-chat / gpt-4.1-mini')).toBeVisible()
  await expect(historySection.getByText('模型切换：gpt-4.1 → gpt-4.1-mini')).toBeVisible()

  await historySection.locator('summary', { hasText: '查看配置 JSON' }).first().click()
  await expect(historySection.locator('pre').first()).toContainText('"gpt-4.1-mini"')
})


test('simulate tab renders conclusion-first cards', async ({ page }) => {
  await openTeacherApp(page)
  await setupRoutingSettingsMocks(page)

  await page.route('http://localhost:8000/teacher/llm-routing/simulate', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        teacher_id: 'teacher',
        context: {
          role: 'teacher',
          skill_id: 'physics-teacher-ops',
          kind: 'chat.agent',
          needs_tools: true,
          needs_json: false,
        },
        decision: {
          enabled: true,
          matched_rule_id: 'rule_teacher_primary',
          reason: '按规则优先级命中 teacher 主链路',
          selected: true,
          candidates: [
            {
              channel_id: 'channel_1',
              provider: 'openai',
              mode: 'openai-chat',
              model: 'gpt-4.1-mini',
              temperature: 0.3,
              max_tokens: 1024,
              capabilities: { tools: true, json: true },
            },
            {
              channel_id: 'channel_backup',
              provider: 'openai',
              mode: 'openai-chat',
              model: 'gpt-4.1',
              temperature: 0.2,
              max_tokens: 1024,
              capabilities: { tools: false, json: true },
            },
          ],
        },
        validation: { errors: [], warnings: [] },
        config_override: true,
        override_validation: { ok: true, errors: [], warnings: [] },
      }),
    })
  })

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '仿真' }).click()

  await page.getByRole('button', { name: '运行仿真' }).click()

  const simPanel = page.locator('.routing-sim-panel')
  await expect(simPanel).toBeVisible()
  await expect(simPanel.getByText('仿真结论')).toBeVisible()
  await expect(simPanel.getByText('目标模型')).toBeVisible()
  await expect(simPanel.getByText('openai / openai-chat / gpt-4.1-mini').first()).toBeVisible()
  await expect(simPanel.locator('summary', { hasText: '候选链路（2）' })).toBeVisible()
})
