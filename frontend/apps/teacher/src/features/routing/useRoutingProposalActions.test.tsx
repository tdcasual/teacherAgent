import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createRoutingProposal,
  fetchRoutingProposalDetail,
  reviewRoutingProposal,
  rollbackRoutingConfig,
  simulateRouting,
} from './routingApi'
import type { RoutingConfig, RoutingProposalDetail } from './routingTypes'
import { useRoutingProposalActions } from './useRoutingProposalActions'

vi.mock('./routingApi', () => ({
  simulateRouting: vi.fn(),
  createRoutingProposal: vi.fn(),
  reviewRoutingProposal: vi.fn(),
  fetchRoutingProposalDetail: vi.fn(),
  rollbackRoutingConfig: vi.fn(),
}))

const simulateRoutingMock = vi.mocked(simulateRouting)
const createRoutingProposalMock = vi.mocked(createRoutingProposal)
const reviewRoutingProposalMock = vi.mocked(reviewRoutingProposal)
const fetchRoutingProposalDetailMock = vi.mocked(fetchRoutingProposalDetail)
const rollbackRoutingConfigMock = vi.mocked(rollbackRoutingConfig)

const draftConfig: RoutingConfig = {
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
      params: { temperature: 0.2, max_tokens: 1024 },
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
}

const createSetters = () => ({
  setBusy: vi.fn(),
  setStatus: vi.fn(),
  setError: vi.fn(),
  setSimResult: vi.fn(),
  setProposalNote: vi.fn(),
  setShowManualReview: vi.fn(),
  setExpandedProposalIds: vi.fn(),
  setProposalDetails: vi.fn(),
  setProposalLoadingMap: vi.fn(),
  setRollbackVersion: vi.fn(),
  setRollbackNote: vi.fn(),
})

const createProps = (overrides?: Partial<Parameters<typeof useRoutingProposalActions>[0]>) => {
  const setters = createSetters()
  const loadOverview = vi.fn(async () => undefined)

  return {
    setters,
    loadOverview,
    props: {
      apiBase: 'http://localhost:8000',
      teacherId: 'teacher-1',
      isLegacyFlat: false,
      draft: draftConfig,
      proposalNote: 'note',
      rollbackNote: 'rollback-note',
      simRole: 'teacher',
      simSkillId: 'physics-teacher-ops',
      simKind: 'chat.agent',
      simNeedsTools: true,
      simNeedsJson: false,
      expandedProposalIds: {},
      proposalDetails: {},
      proposalLoadingMap: {},
      loadOverview,
      ...setters,
      ...overrides,
    },
  }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useRoutingProposalActions', () => {
  it('runs simulate and updates result/status', async () => {
    const { props, setters } = createProps()
    simulateRoutingMock.mockResolvedValue({
      ok: true,
      teacher_id: 'teacher-1',
      context: { needs_tools: true, needs_json: false },
      decision: { enabled: true, matched_rule_id: 'rule_primary', reason: 'ok', selected: true, candidates: [] },
      validation: { errors: [], warnings: [] },
    })
    const { result } = renderHook(() => useRoutingProposalActions(props))

    await act(async () => {
      await result.current.handleSimulate()
    })

    expect(simulateRoutingMock).toHaveBeenCalledWith('http://localhost:8000', expect.objectContaining({ teacher_id: 'teacher-1' }))
    expect(setters.setSimResult).toHaveBeenCalled()
    expect(setters.setStatus).toHaveBeenCalledWith('仿真完成。')
    expect(setters.setBusy).toHaveBeenNthCalledWith(1, true)
    expect(setters.setBusy).toHaveBeenLastCalledWith(false)
  })

  it('creates proposal in legacy mode and enables manual review', async () => {
    const { props, setters, loadOverview } = createProps({ isLegacyFlat: true })
    createRoutingProposalMock.mockResolvedValue({ ok: true, proposal_id: 'p-1', status: 'pending' })
    const { result } = renderHook(() => useRoutingProposalActions(props))

    await act(async () => {
      await result.current.handlePropose()
    })

    expect(createRoutingProposalMock).toHaveBeenCalled()
    expect(setters.setStatus).toHaveBeenCalledWith('提案已创建：p-1')
    expect(setters.setProposalNote).toHaveBeenCalledWith('')
    expect(setters.setShowManualReview).toHaveBeenCalledWith(true)
    expect(loadOverview).toHaveBeenCalledWith({ silent: true })
    expect(reviewRoutingProposalMock).not.toHaveBeenCalled()
  })

  it('auto-applies proposal in non-legacy mode', async () => {
    const { props, setters, loadOverview } = createProps()
    createRoutingProposalMock.mockResolvedValue({ ok: true, proposal_id: 'p-2', status: 'pending' })
    reviewRoutingProposalMock.mockResolvedValue({ ok: true, proposal_id: 'p-2', status: 'approved', version: 12 })
    const { result } = renderHook(() => useRoutingProposalActions(props))

    await act(async () => {
      await result.current.handlePropose()
    })

    expect(reviewRoutingProposalMock).toHaveBeenCalledWith('http://localhost:8000', 'p-2', {
      teacher_id: 'teacher-1',
      approve: true,
    })
    expect(setters.setStatus).toHaveBeenCalledWith('配置已生效（v12）')
    expect(loadOverview).toHaveBeenCalledWith({ silent: true, forceReplaceDraft: true })
  })

  it('loads proposal detail only when expanding and no cache exists', async () => {
    const detail: RoutingProposalDetail = {
      ok: true,
      teacher_id: 'teacher-1',
      config_path: '/tmp/routing.json',
      proposal: { proposal_id: 'p-3' },
    }
    const { props, setters } = createProps()
    fetchRoutingProposalDetailMock.mockResolvedValue(detail)
    const { result } = renderHook(() => useRoutingProposalActions(props))

    await act(async () => {
      await result.current.handleToggleProposalDetail('p-3')
    })

    expect(fetchRoutingProposalDetailMock).toHaveBeenCalledWith('http://localhost:8000', 'p-3', 'teacher-1')
    expect(setters.setExpandedProposalIds).toHaveBeenCalled()
    expect(setters.setProposalLoadingMap).toHaveBeenCalled()
    expect(setters.setProposalDetails).toHaveBeenCalled()
  })

  it('rolls back and refreshes overview', async () => {
    const { props, setters, loadOverview } = createProps({ rollbackNote: 'rollback please' })
    rollbackRoutingConfigMock.mockResolvedValue({ ok: true, version: 9 })
    const { result } = renderHook(() => useRoutingProposalActions(props))

    await act(async () => {
      await result.current.handleRollback(9)
    })

    expect(rollbackRoutingConfigMock).toHaveBeenCalledWith('http://localhost:8000', {
      teacher_id: 'teacher-1',
      target_version: 9,
      note: 'rollback please',
    })
    expect(setters.setStatus).toHaveBeenCalledWith('已回滚到版本 9')
    expect(setters.setRollbackVersion).toHaveBeenCalledWith('')
    expect(setters.setRollbackNote).toHaveBeenCalledWith('')
    expect(loadOverview).toHaveBeenCalledWith({ silent: true, forceReplaceDraft: true })
  })
})
