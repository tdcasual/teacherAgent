import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchProviderRegistry, fetchRoutingOverview } from './routingApi'
import type { RoutingConfig, RoutingOverview, TeacherProviderRegistryOverview } from './routingTypes'
import { useRoutingOverviewSync } from './useRoutingOverviewSync'

vi.mock('./routingApi', () => ({
  fetchRoutingOverview: vi.fn(),
  fetchProviderRegistry: vi.fn(),
}))

const fetchRoutingOverviewMock = vi.mocked(fetchRoutingOverview)
const fetchProviderRegistryMock = vi.mocked(fetchProviderRegistry)

const makeRoutingConfig = (): RoutingConfig => ({
  schema_version: 1,
  enabled: true,
  version: 3,
  updated_at: '2026-02-14T10:00:00Z',
  updated_by: 'teacher-admin',
  channels: [
    {
      id: 'primary',
      title: 'Primary',
      target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
      params: { temperature: 0.2, max_tokens: 1200 },
      fallback_channels: [],
      capabilities: { tools: true, json: true },
    },
  ],
  rules: [
    {
      id: 'rule_primary',
      priority: 100,
      enabled: true,
      match: { roles: ['teacher'], skills: [], kinds: [], needs_tools: undefined, needs_json: undefined },
      route: { channel_id: 'primary' },
    },
  ],
})

const makeOverview = (): RoutingOverview => ({
  ok: true,
  teacher_id: 'teacher-1',
  routing: makeRoutingConfig(),
  validation: { errors: [], warnings: [] },
  history: [],
  proposals: [],
  catalog: {
    providers: [
      {
        provider: 'openai',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
  config_path: '/tmp/routing.json',
})

const makeProviderOverview = (): TeacherProviderRegistryOverview => ({
  ok: true,
  teacher_id: 'teacher-1',
  providers: [
    {
      id: 'provider_openai',
      provider: 'openai',
      display_name: 'OpenAI Main',
      base_url: 'https://api.openai.com/v1',
      api_key_masked: 'sk-***',
      default_mode: 'openai-chat',
      default_model: 'gpt-4.1-mini',
      enabled: true,
      source: 'private',
    },
  ],
  shared_catalog: {
    providers: [
      {
        provider: 'openai',
        base_url: 'https://api.openai.com/v1',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
  catalog: {
    providers: [
      {
        provider: 'openai',
        base_url: 'https://api.openai.com/v1',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
  config_path: '/tmp/providers.json',
})

const createSetters = () => ({
  setLoading: vi.fn(),
  setError: vi.fn(),
  setOverview: vi.fn(),
  setDraft: vi.fn(),
  setHasLocalEdits: vi.fn(),
  setProviderOverview: vi.fn(),
  setProviderEditMap: vi.fn(),
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useRoutingOverviewSync', () => {
  it('loads overview and provider registry on mount', async () => {
    const setters = createSetters()
    const cloneConfig = vi.fn((config: RoutingConfig) => ({ ...config }))
    const overview = makeOverview()
    const providerOverview = makeProviderOverview()
    fetchRoutingOverviewMock.mockResolvedValue(overview)
    fetchProviderRegistryMock.mockResolvedValue(providerOverview)

    renderHook(() =>
      useRoutingOverviewSync({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        hasLocalEdits: false,
        providerOverview: null,
        cloneConfig,
        ...setters,
      }),
    )

    await waitFor(() => expect(fetchRoutingOverviewMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(fetchProviderRegistryMock).toHaveBeenCalledTimes(1))

    expect(setters.setLoading).toHaveBeenNthCalledWith(1, true)
    expect(setters.setLoading).toHaveBeenLastCalledWith(false)
    expect(setters.setOverview).toHaveBeenCalledWith(overview)
    expect(setters.setProviderOverview).toHaveBeenCalledWith(providerOverview)
    expect(cloneConfig).toHaveBeenCalledWith(overview.routing)
    expect(setters.setDraft).toHaveBeenCalled()
    expect(setters.setHasLocalEdits).toHaveBeenCalledWith(false)
  })

  it('does not replace draft when local edits exist and no force flag', async () => {
    const setters = createSetters()
    const cloneConfig = vi.fn((config: RoutingConfig) => ({ ...config }))
    fetchRoutingOverviewMock.mockResolvedValue(makeOverview())
    fetchProviderRegistryMock.mockResolvedValue(makeProviderOverview())

    const { result } = renderHook(() =>
      useRoutingOverviewSync({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        hasLocalEdits: true,
        providerOverview: null,
        cloneConfig,
        ...setters,
      }),
    )

    await waitFor(() => expect(fetchRoutingOverviewMock).toHaveBeenCalledTimes(1))
    setters.setDraft.mockClear()
    setters.setHasLocalEdits.mockClear()

    const loadingCallsBefore = setters.setLoading.mock.calls.length
    await act(async () => {
      await result.current.loadOverview({ silent: true })
    })

    expect(setters.setLoading.mock.calls.length).toBe(loadingCallsBefore)
    expect(setters.setDraft).not.toHaveBeenCalled()
    expect(setters.setHasLocalEdits).not.toHaveBeenCalled()
  })

  it('polls every 30 seconds using silent refresh', async () => {
    vi.useFakeTimers()

    const setters = createSetters()
    const cloneConfig = vi.fn((config: RoutingConfig) => ({ ...config }))
    fetchRoutingOverviewMock.mockResolvedValue(makeOverview())
    fetchProviderRegistryMock.mockResolvedValue(makeProviderOverview())

    const { unmount } = renderHook(() =>
      useRoutingOverviewSync({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        hasLocalEdits: false,
        providerOverview: null,
        cloneConfig,
        ...setters,
      }),
    )

    await act(async () => {
      await Promise.resolve()
    })
    expect(fetchRoutingOverviewMock).toHaveBeenCalledTimes(1)
    expect(fetchProviderRegistryMock).toHaveBeenCalledTimes(1)
    const loadingCallsAfterInitialLoad = setters.setLoading.mock.calls.length
    fetchRoutingOverviewMock.mockClear()
    fetchProviderRegistryMock.mockClear()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000)
    })

    expect(fetchRoutingOverviewMock).toHaveBeenCalledTimes(1)
    expect(fetchProviderRegistryMock).toHaveBeenCalledTimes(1)
    expect(setters.setLoading.mock.calls.length).toBe(loadingCallsAfterInitialLoad)

    unmount()
  })
})
