import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RoutingCatalogProvider, RoutingConfig, RoutingOverview } from './routingTypes'
import { useRoutingDraftActions } from './useRoutingDraftActions'

const makeDraft = (): RoutingConfig => ({
  schema_version: 1,
  enabled: true,
  version: 1,
  updated_at: '2026-02-14T10:00:00Z',
  updated_by: 'teacher-admin',
  channels: [
    {
      id: 'primary',
      title: 'Primary',
      target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
      params: { temperature: 0.3, max_tokens: 1024 },
      fallback_channels: ['backup'],
      capabilities: { tools: true, json: true },
    },
    {
      id: 'backup',
      title: 'Backup',
      target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
      params: { temperature: 0.2, max_tokens: 512 },
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

const providers: RoutingCatalogProvider[] = [
  {
    provider: 'openai',
    modes: [{ mode: 'openai-chat', default_model: 'gpt-4.1-mini', model_env: 'OPENAI_MODEL' }],
  },
]

const makeOverview = (): RoutingOverview => ({
  ok: true,
  teacher_id: 'teacher-1',
  routing: makeDraft(),
  validation: { errors: [], warnings: [] },
  history: [],
  proposals: [],
  catalog: {
    providers,
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
  config_path: '/tmp/routing.json',
})

const createSetters = () => ({
  setTeacherId: vi.fn(),
  setDraft: vi.fn(),
  setHasLocalEdits: vi.fn(),
  setStatus: vi.fn(),
  setError: vi.fn(),
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useRoutingDraftActions', () => {
  it('blocks teacher switch when user cancels confirmation', () => {
    const setters = createSetters()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    const { result } = renderHook(() =>
      useRoutingDraftActions({
        teacherId: 'teacher-1',
        hasLocalEdits: true,
        draft: makeDraft(),
        overview: makeOverview(),
        providers,
        providerModeMap: new Map([['openai', ['openai-chat']]]),
        cloneConfig: (config: RoutingConfig) => ({ ...config }),
        ...setters,
      }),
    )

    act(() => {
      result.current.handleTeacherIdChange('teacher-2')
    })

    expect(confirmSpy).toHaveBeenCalled()
    expect(setters.setTeacherId).not.toHaveBeenCalled()
  })

  it('adds channel through setDraft updater and marks local edits', () => {
    const setters = createSetters()

    const { result } = renderHook(() =>
      useRoutingDraftActions({
        teacherId: 'teacher-1',
        hasLocalEdits: false,
        draft: makeDraft(),
        overview: makeOverview(),
        providers,
        providerModeMap: new Map([['openai', ['openai-chat']]]),
        cloneConfig: (config: RoutingConfig) => ({ ...config }),
        ...setters,
      }),
    )

    act(() => {
      result.current.addChannel()
    })

    const updaterCall = setters.setDraft.mock.calls[setters.setDraft.mock.calls.length - 1]
    const updater = updaterCall?.[0] as (prev: RoutingConfig) => RoutingConfig
    const next = updater({ ...makeDraft(), channels: [] })
    expect(next.channels).toHaveLength(1)
    expect(next.channels[0]?.target.provider).toBe('openai')
    expect(next.channels[0]?.target.mode).toBe('openai-chat')
    expect(setters.setHasLocalEdits).toHaveBeenCalledWith(true)
  })

  it('re-routes rules when removing the currently targeted channel', () => {
    const setters = createSetters()

    const { result } = renderHook(() =>
      useRoutingDraftActions({
        teacherId: 'teacher-1',
        hasLocalEdits: false,
        draft: makeDraft(),
        overview: makeOverview(),
        providers,
        providerModeMap: new Map([['openai', ['openai-chat']]]),
        cloneConfig: (config: RoutingConfig) => ({ ...config }),
        ...setters,
      }),
    )

    act(() => {
      result.current.removeChannel(0)
    })

    const updaterCall = setters.setDraft.mock.calls[setters.setDraft.mock.calls.length - 1]
    const updater = updaterCall?.[0] as (prev: RoutingConfig) => RoutingConfig
    const next = updater(makeDraft())
    expect(next.channels.map((channel) => channel.id)).toEqual(['backup'])
    expect(next.rules[0]?.route.channel_id).toBe('backup')
  })

  it('resets draft from overview clone and clears draft status', () => {
    const setters = createSetters()
    const cloned = { ...makeDraft(), version: 99 }
    const cloneConfig = vi.fn(() => cloned)

    const { result } = renderHook(() =>
      useRoutingDraftActions({
        teacherId: 'teacher-1',
        hasLocalEdits: true,
        draft: makeDraft(),
        overview: makeOverview(),
        providers,
        providerModeMap: new Map([['openai', ['openai-chat']]]),
        cloneConfig,
        ...setters,
      }),
    )

    act(() => {
      result.current.handleResetDraft()
    })

    expect(cloneConfig).toHaveBeenCalled()
    expect(setters.setDraft).toHaveBeenCalledWith(cloned)
    expect(setters.setHasLocalEdits).toHaveBeenCalledWith(false)
    expect(setters.setStatus).toHaveBeenCalledWith('已恢复为线上配置。')
    expect(setters.setError).toHaveBeenCalledWith('')
  })
})
