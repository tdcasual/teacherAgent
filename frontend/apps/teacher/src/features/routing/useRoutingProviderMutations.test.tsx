import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createProviderRegistryItem,
  deleteProviderRegistryItem,
  probeProviderRegistryModels,
  updateProviderRegistryItem,
} from './routingApi'
import type { TeacherProviderRegistryOverview } from './routingTypes'
import { useRoutingProviderMutations } from './useRoutingProviderMutations'

vi.mock('./routingApi', () => ({
  createProviderRegistryItem: vi.fn(),
  updateProviderRegistryItem: vi.fn(),
  deleteProviderRegistryItem: vi.fn(),
  probeProviderRegistryModels: vi.fn(),
}))

const createProviderRegistryItemMock = vi.mocked(createProviderRegistryItem)
const updateProviderRegistryItemMock = vi.mocked(updateProviderRegistryItem)
const deleteProviderRegistryItemMock = vi.mocked(deleteProviderRegistryItem)
const probeProviderRegistryModelsMock = vi.mocked(probeProviderRegistryModels)

const makeProviderOverview = (): TeacherProviderRegistryOverview => ({
  ok: true,
  teacher_id: 'teacher-1',
  providers: [
    {
      id: 'provider_openai',
      provider: 'openai',
      display_name: 'OpenAI Main',
      base_url: 'https://proxy.example.com/v1',
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
        base_url: 'https://proxy.example.com/v1',
        modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
      },
    ],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
  config_path: '/tmp/providers.json',
})

const createSetters = () => ({
  setProviderBusy: vi.fn(),
  setError: vi.fn(),
  setStatus: vi.fn(),
  setProviderCreateForm: vi.fn(),
  setProviderAddMode: vi.fn(),
  setProviderAddPreset: vi.fn(),
  setProviderProbeMap: vi.fn(),
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useRoutingProviderMutations', () => {
  it('creates provider with catalog base_url fallback and refreshes overview', async () => {
    const setters = createSetters()
    const loadOverview = vi.fn(async () => undefined)
    createProviderRegistryItemMock.mockResolvedValue({
      ok: true,
      provider_id: 'openai',
    })

    const { result } = renderHook(() =>
      useRoutingProviderMutations({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        providerOverview: makeProviderOverview(),
        providerCreateForm: {
          provider_id: 'openai',
          display_name: 'OpenAI Main',
          base_url: '',
          api_key: 'sk-live',
          default_model: 'gpt-4.1-mini',
          enabled: true,
        },
        providerEditMap: {},
        loadOverview,
        ...setters,
      }),
    )

    await act(async () => {
      await result.current.handleCreateProvider()
    })

    expect(createProviderRegistryItemMock).toHaveBeenCalledWith('http://localhost:8000', {
      teacher_id: 'teacher-1',
      provider_id: 'openai',
      display_name: 'OpenAI Main',
      base_url: 'https://api.openai.com/v1',
      api_key: 'sk-live',
      default_model: 'gpt-4.1-mini',
      enabled: true,
    })
    expect(setters.setProviderCreateForm).toHaveBeenCalledWith({
      provider_id: '',
      display_name: '',
      base_url: '',
      api_key: '',
      default_model: '',
      enabled: true,
    })
    expect(setters.setProviderAddMode).toHaveBeenCalledWith('')
    expect(setters.setProviderAddPreset).toHaveBeenCalledWith('')
    expect(setters.setStatus).toHaveBeenCalledWith('Provider 已新增并即时生效。')
    expect(loadOverview).toHaveBeenCalledWith({ silent: true })
    expect(setters.setProviderBusy).toHaveBeenNthCalledWith(1, true)
    expect(setters.setProviderBusy).toHaveBeenLastCalledWith(false)
  })

  it('rejects create when api_key or base_url is missing', async () => {
    const setters = createSetters()
    const loadOverview = vi.fn(async () => undefined)

    const { result } = renderHook(() =>
      useRoutingProviderMutations({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        providerOverview: null,
        providerCreateForm: {
          provider_id: 'custom',
          display_name: 'Custom',
          base_url: '',
          api_key: '',
          default_model: '',
          enabled: true,
        },
        providerEditMap: {},
        loadOverview,
        ...setters,
      }),
    )

    await act(async () => {
      await result.current.handleCreateProvider()
    })

    expect(setters.setError).toHaveBeenCalledWith('新增 Provider 需要填写 base_url 和 api_key')
    expect(createProviderRegistryItemMock).not.toHaveBeenCalled()
    expect(loadOverview).not.toHaveBeenCalled()
  })

  it('updates provider and only sends api_key when provided', async () => {
    const setters = createSetters()
    const loadOverview = vi.fn(async () => undefined)
    updateProviderRegistryItemMock.mockResolvedValue({ ok: true, provider_id: 'openai' })

    const { result } = renderHook(() =>
      useRoutingProviderMutations({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        providerOverview: makeProviderOverview(),
        providerCreateForm: {
          provider_id: '',
          display_name: '',
          base_url: '',
          api_key: '',
          default_model: '',
          enabled: true,
        },
        providerEditMap: {
          openai: {
            display_name: ' OpenAI Main ',
            base_url: ' https://proxy.example.com/v1 ',
            enabled: true,
            api_key: '',
            default_model: ' ',
          },
        },
        loadOverview,
        ...setters,
      }),
    )

    await act(async () => {
      await result.current.handleUpdateProvider('openai')
    })

    const payload = updateProviderRegistryItemMock.mock.calls[0]?.[2]
    expect(updateProviderRegistryItemMock).toHaveBeenCalledWith('http://localhost:8000', 'openai', expect.any(Object))
    expect(payload).toMatchObject({
      teacher_id: 'teacher-1',
      display_name: 'OpenAI Main',
      base_url: 'https://proxy.example.com/v1',
      enabled: true,
      default_model: undefined,
    })
    expect(payload).not.toHaveProperty('api_key')
    expect(setters.setStatus).toHaveBeenCalledWith('Provider openai 已更新。')
    expect(loadOverview).toHaveBeenCalledWith({ silent: true })
  })

  it('probes provider models and stores top 12 entries', async () => {
    const setters = createSetters()
    const loadOverview = vi.fn(async () => undefined)
    probeProviderRegistryModelsMock.mockResolvedValue({
      ok: true,
      models: Array.from({ length: 14 }, (_, index) => `model-${index + 1}`),
    })

    const { result } = renderHook(() =>
      useRoutingProviderMutations({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        providerOverview: makeProviderOverview(),
        providerCreateForm: {
          provider_id: '',
          display_name: '',
          base_url: '',
          api_key: '',
          default_model: '',
          enabled: true,
        },
        providerEditMap: {},
        loadOverview,
        ...setters,
      }),
    )

    await act(async () => {
      await result.current.handleProbeProviderModels('openai')
    })

    expect(probeProviderRegistryModelsMock).toHaveBeenCalledWith('http://localhost:8000', 'openai', {
      teacher_id: 'teacher-1',
    })
    expect(setters.setProviderProbeMap).toHaveBeenCalled()
    const updaterCall = setters.setProviderProbeMap.mock.calls[setters.setProviderProbeMap.mock.calls.length - 1]
    const updater = updaterCall?.[0] as (prev: Record<string, string>) => Record<string, string>
    const next = updater({ existing: 'keep' })
    expect(next.existing).toBe('keep')
    expect(next.openai).toBe(
      Array.from({ length: 12 }, (_, index) => `model-${index + 1}`).join('，'),
    )
    expect(setters.setStatus).toHaveBeenCalledWith('Provider openai 探测完成。')
  })

  it('disables provider and refreshes overview', async () => {
    const setters = createSetters()
    const loadOverview = vi.fn(async () => undefined)
    deleteProviderRegistryItemMock.mockResolvedValue({ ok: true, provider_id: 'openai' })

    const { result } = renderHook(() =>
      useRoutingProviderMutations({
        apiBase: 'http://localhost:8000',
        teacherId: 'teacher-1',
        providerOverview: makeProviderOverview(),
        providerCreateForm: {
          provider_id: '',
          display_name: '',
          base_url: '',
          api_key: '',
          default_model: '',
          enabled: true,
        },
        providerEditMap: {},
        loadOverview,
        ...setters,
      }),
    )

    await act(async () => {
      await result.current.handleDisableProvider('openai')
    })

    expect(deleteProviderRegistryItemMock).toHaveBeenCalledWith('http://localhost:8000', 'openai', {
      teacher_id: 'teacher-1',
    })
    expect(setters.setStatus).toHaveBeenCalledWith('Provider openai 已禁用。')
    expect(loadOverview).toHaveBeenCalledWith({ silent: true })
  })
})
