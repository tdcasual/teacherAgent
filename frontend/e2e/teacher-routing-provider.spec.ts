import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'
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

const buildRoutingOverview = (args?: {
  version?: number
  proposalId?: string
  includePending?: boolean
}) => ({
  ok: true,
  teacher_id: 'T001',
  routing: {
    schema_version: 1,
    enabled: true,
    version: args?.version ?? 7,
    updated_at: new Date().toISOString(),
    updated_by: 'e2e',
    channels: [
      {
        id: 'channel_1',
        title: '渠道 1',
        target: {
          provider: 'openai',
          mode: 'openai-chat',
          model: 'gpt-4.1-mini',
        },
        params: { temperature: 0.3, max_tokens: 2048 },
        fallback_channels: [],
        capabilities: { tools: true, json: true },
      },
    ],
    rules: [
      {
        id: 'rule_teacher_chat',
        priority: 10,
        enabled: true,
        match: {
          roles: ['teacher'],
          skills: [],
          kinds: ['chat.agent'],
          needs_tools: true,
          needs_json: false,
        },
        route: { channel_id: 'channel_1' },
      },
    ],
  },
  validation: { errors: [], warnings: [] },
  history: [
    {
      file: 'v3.json',
      version: 3,
      saved_at: '2026-02-07T00:00:00.000Z',
      saved_by: 'teacher',
      source: 'proposal',
      note: 'stable',
    },
  ],
  proposals:
    args?.includePending === false
      ? []
      : [
          {
            proposal_id: args?.proposalId || 'prop_pending_1',
            created_at: '2026-02-07T10:00:00.000Z',
            created_by: 'teacher',
            status: 'pending',
            note: 'pending review',
            validation_ok: true,
            proposal_path: '/tmp/prop_pending_1.json',
          },
        ],
  catalog: sharedCatalog,
  config_path: '/tmp/routing.json',
})

const buildProviderOverview = (providers: Array<Record<string, unknown>> = []) => ({
  ok: true,
  teacher_id: 'T001',
  providers,
  shared_catalog: sharedCatalog,
  catalog: sharedCatalog,
  config_path: '/tmp/provider-registry.json',
})

const openRoutingPageWithMocks = async (
  page: Parameters<MatrixCaseRunner>[0]['page'],
  options?: {
    routing?: () => Record<string, unknown>
    providers?: () => Record<string, unknown>
    onRequest?: (request: { pathname: string; method: string; bodyText: string }) => Promise<{ status?: number; body?: unknown } | void>
  },
) => {
  await openTeacherApp(page)

  await page.route('http://localhost:8000/teacher/llm-routing**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const pathname = url.pathname
    const bodyText = request.postData() || ''

    const custom = await options?.onRequest?.({ pathname, method, bodyText })
    if (custom) {
      await route.fulfill({
        status: custom.status || 200,
        contentType: 'application/json',
        body: JSON.stringify(custom.body || { ok: true }),
      })
      return
    }

    if (method === 'GET' && pathname === '/teacher/llm-routing') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(options?.routing ? options.routing() : buildRoutingOverview()),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  await page.route('http://localhost:8000/teacher/provider-registry**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const pathname = url.pathname
    const bodyText = request.postData() || ''

    const custom = await options?.onRequest?.({ pathname, method, bodyText })
    if (custom) {
      await route.fulfill({
        status: custom.status || 200,
        contentType: 'application/json',
        body: JSON.stringify(custom.body || { ok: true }),
      })
      return
    }

    if (method === 'GET' && pathname === '/teacher/provider-registry') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(options?.providers ? options.providers() : buildProviderOverview()),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  await page.getByRole('button', { name: '模型路由', exact: true }).click()
  await expect(page.locator('.routing-page')).toBeVisible()
}

const routingProviderCases: MatrixCase[] = [
  {
    id: 'F001',
    priority: 'P0',
    title: 'Routing page loads when routing and provider endpoints succeed',
    given: '/teacher/llm-routing and /teacher/provider-registry return success',
    when: 'Open the routing page',
    then: 'Page renders with actionable controls',
  },
  {
    id: 'F002',
    priority: 'P1',
    title: 'Provider failure degrades gracefully when routing succeeds',
    given: 'Routing endpoint succeeds and provider endpoint fails',
    when: 'Open the routing page',
    then: 'Provider area shows fallback error without page crash',
  },
  {
    id: 'F003',
    priority: 'P1',
    title: 'Routing failure degrades gracefully when provider succeeds',
    given: 'Provider endpoint succeeds and routing endpoint fails',
    when: 'Open the routing page',
    then: 'Routing area shows fallback error and supports retry',
  },
  {
    id: 'F004',
    priority: 'P0',
    title: 'Simulate request returns matched rule and channel',
    given: '/teacher/llm-routing/simulate is available',
    when: 'Run simulation from routing UI',
    then: 'Simulation result includes selected rule and target channel',
  },
  {
    id: 'F005',
    priority: 'P0',
    title: 'Create proposal appends item to proposal list',
    given: 'Proposal creation endpoint is available',
    when: 'Submit new routing proposal',
    then: 'New proposal appears in proposal list',
  },
  {
    id: 'F006',
    priority: 'P0',
    title: 'Approve proposal increments active version',
    given: 'A proposal is pending review',
    when: 'Review with approve action',
    then: 'Routing version increments and proposal is marked applied',
  },
  {
    id: 'F007',
    priority: 'P1',
    title: 'Reject proposal stores status and reason',
    given: 'A proposal is pending review',
    when: 'Review with reject action and reason',
    then: 'Proposal status is rejected with visible reason',
  },
  {
    id: 'F008',
    priority: 'P0',
    title: 'Rollback activates selected historical version',
    given: 'Routing history includes multiple versions',
    when: 'Run rollback to previous version',
    then: 'Current routing config reflects selected historical version',
  },
  {
    id: 'F009',
    priority: 'P0',
    title: 'Valid https provider can be created',
    given: 'New provider form has valid https base_url and key',
    when: 'Submit provider create',
    then: 'Provider appears and key is masked in response UI',
  },
  {
    id: 'F010',
    priority: 'P0',
    title: 'Provider id conflict against shared catalog is blocked',
    given: 'Provider id matches shared provider id',
    when: 'Submit provider create',
    then: 'UI shows conflict error and provider is not created',
  },
  {
    id: 'F011',
    priority: 'P1',
    title: 'Provider key rotation does not expose plaintext key',
    given: 'Provider exists and patch endpoint is available',
    when: 'Submit provider update with new api_key',
    then: 'Update succeeds and plaintext key is never displayed',
  },
  {
    id: 'F012',
    priority: 'P1',
    title: 'Provider delete performs soft disable',
    given: 'Provider exists and delete endpoint is available',
    when: 'Delete provider',
    then: 'Provider is no longer selectable in merged catalog',
  },
  {
    id: 'F013',
    priority: 'P1',
    title: 'Probe models success returns selectable model list',
    given: 'Provider supports upstream /models',
    when: 'Run probe-models action',
    then: 'Model list is returned and can be selected',
  },
  {
    id: 'F014',
    priority: 'P1',
    title: 'Probe models timeout does not block manual model entry',
    given: 'Probe-models call times out or fails',
    when: 'Attempt to configure model manually',
    then: 'Manual model entry remains enabled',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  F001: async ({ page }) => {
    await openRoutingPageWithMocks(page)
    await expect(page.getByRole('heading', { name: '模型路由配置' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Provider 管理（共享 + 私有）' })).toBeVisible()
  },

  F004: async ({ page }) => {
    let simulateCalls = 0

    await openRoutingPageWithMocks(page, {
      onRequest: async ({ pathname, method }) => {
        if (method === 'POST' && pathname === '/teacher/llm-routing/simulate') {
          simulateCalls += 1
          return {
            body: {
              ok: true,
              teacher_id: 'T001',
              context: {
                role: 'teacher',
                skill_id: 'physics-teacher-ops',
                kind: 'chat.agent',
                needs_tools: true,
                needs_json: false,
              },
              decision: {
                enabled: true,
                matched_rule_id: 'rule_teacher_chat',
                reason: 'matched by role and kind',
                selected: true,
                candidates: [
                  {
                    channel_id: 'channel_1',
                    provider: 'openai',
                    mode: 'openai-chat',
                    model: 'gpt-4.1-mini',
                    temperature: 0.3,
                    max_tokens: 2048,
                    capabilities: { tools: true, json: true },
                  },
                ],
              },
              validation: { errors: [], warnings: [] },
            },
          }
        }
      },
    })

    await page.getByRole('button', { name: '运行仿真' }).click()

    await expect.poll(() => simulateCalls).toBe(1)
    await expect(page.getByText('命中规则：rule_teacher_chat')).toBeVisible()
    await expect(page.getByText('候选渠道：channel_1')).toBeVisible()
  },

  F005: async ({ page }) => {
    let proposalCreated = false

    await openRoutingPageWithMocks(page, {
      routing: () => buildRoutingOverview({ proposalId: proposalCreated ? 'prop_new_1' : 'prop_pending_1', includePending: true }),
      onRequest: async ({ pathname, method }) => {
        if (method === 'POST' && pathname === '/teacher/llm-routing/proposals') {
          proposalCreated = true
          return {
            body: {
              ok: true,
              proposal_id: 'prop_new_1',
              status: 'pending',
              validation: { ok: true, errors: [], warnings: [] },
            },
          }
        }
      },
    })

    await page.getByRole('button', { name: '提交提案' }).click()

    await expect(page.getByText('提案已提交')).toBeVisible()
    await expect(page.getByText('prop_new_1')).toBeVisible()
  },

  F006: async ({ page }) => {
    let approved = false
    let version = 7

    await openRoutingPageWithMocks(page, {
      routing: () => buildRoutingOverview({ version, proposalId: 'prop_review_1', includePending: !approved }),
      onRequest: async ({ pathname, method }) => {
        if (method === 'POST' && pathname === '/teacher/llm-routing/proposals/prop_review_1/review') {
          approved = true
          version = 8
          return {
            body: {
              ok: true,
              proposal_id: 'prop_review_1',
              status: 'approved',
              version: 8,
            },
          }
        }
      },
    })

    await page.getByRole('button', { name: '生效' }).first().click()

    await expect(page.getByText('提案已生效')).toBeVisible()
    await expect(page.getByText('线上版本：8')).toBeVisible()
  },

  F008: async ({ page }) => {
    let version = 7

    await openRoutingPageWithMocks(page, {
      routing: () => buildRoutingOverview({ version, proposalId: 'prop_pending_1', includePending: true }),
      onRequest: async ({ pathname, method, bodyText }) => {
        if (method === 'POST' && pathname === '/teacher/llm-routing/rollback') {
          const payload = JSON.parse(bodyText || '{}')
          version = Number(payload.target_version || 3)
          return { body: { ok: true, version } }
        }
      },
    })

    await page.getByPlaceholder('例如：3').fill('3')
    await page.getByRole('button', { name: '回滚到指定版本' }).click()

    await expect(page.getByText('回滚成功')).toBeVisible()
    await expect(page.getByText('线上版本：3')).toBeVisible()
  },

  F009: async ({ page }) => {
    let providers: Array<Record<string, unknown>> = []

    await openRoutingPageWithMocks(page, {
      providers: () => buildProviderOverview(providers),
      onRequest: async ({ pathname, method, bodyText }) => {
        if (method === 'POST' && pathname === '/teacher/provider-registry/providers') {
          const payload = JSON.parse(bodyText || '{}')
          const providerId = payload.provider_id || 'tprv_proxy_main'
          providers = [
            {
              id: providerId,
              provider: providerId,
              display_name: payload.display_name || '主中转',
              base_url: payload.base_url,
              api_key_masked: 'sk-***abcd',
              default_mode: 'openai-chat',
              default_model: payload.default_model || 'gpt-4.1-mini',
              enabled: payload.enabled !== false,
              source: 'private',
            },
          ]
          return { body: { ok: true, provider: providers[0] } }
        }
      },
    })

    await page.getByPlaceholder('例如：tprv_proxy_main').fill('tprv_proxy_main')
    await page.getByPlaceholder('例如：主中转').fill('主中转')
    await page.getByPlaceholder('例如：https://proxy.example.com/v1').fill('https://proxy.example.com/v1')
    await page.getByPlaceholder('仅提交时可见，后续仅显示掩码').fill('sk-test-key')
    await page.getByPlaceholder('例如：gpt-4.1-mini').fill('gpt-4.1-mini')
    await page.getByRole('button', { name: '新增 Provider' }).click()

    await expect(page.getByText('Provider 已新增')).toBeVisible()
    await expect(page.getByText('tprv_proxy_main')).toBeVisible()
    await expect(page.getByText('key: sk-***abcd')).toBeVisible()
  },

  F010: async ({ page }) => {
    await openRoutingPageWithMocks(page, {
      onRequest: async ({ pathname, method }) => {
        if (method === 'POST' && pathname === '/teacher/provider-registry/providers') {
          return {
            status: 409,
            body: { detail: 'provider id conflict: openai' },
          }
        }
      },
    })

    await page.getByPlaceholder('例如：tprv_proxy_main').fill('openai')
    await page.getByPlaceholder('例如：主中转').fill('冲突中转')
    await page.getByPlaceholder('例如：https://proxy.example.com/v1').fill('https://proxy.example.com/v1')
    await page.getByPlaceholder('仅提交时可见，后续仅显示掩码').fill('sk-test-key')
    await page.getByRole('button', { name: '新增 Provider' }).click()

    await expect(page.getByText('provider id conflict')).toBeVisible()
    await expect(page.getByText('暂无私有 Provider。')).toBeVisible()
  },
}

registerMatrixCases('Teacher Routing and Provider Management', routingProviderCases, implementations)
