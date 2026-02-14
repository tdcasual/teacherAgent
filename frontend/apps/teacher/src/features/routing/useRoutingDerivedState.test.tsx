import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RoutingHistorySummary, RoutingOverview } from './routingTypes'
import { useRoutingDerivedState } from './useRoutingDerivedState'

const summary = (overrides?: Partial<RoutingHistorySummary>): RoutingHistorySummary => ({
  enabled: true,
  channel_count: 2,
  rule_count: 2,
  primary_channel_id: 'c-main',
  primary_channel_title: 'Main',
  primary_provider: 'openai',
  primary_mode: 'openai-chat',
  primary_model: 'gpt-4.1-mini',
  top_rule_id: 'rule-main',
  ...overrides,
})

const overviewFixture = (validationErrors: string[] = []): RoutingOverview => ({
  ok: true,
  teacher_id: 'teacher-1',
  config_path: '/tmp/routing.json',
  routing: {
    schema_version: 1,
    enabled: true,
    version: 12,
    updated_at: '2026-02-14T12:00:00Z',
    updated_by: 'teacher-admin',
    channels: [
      {
        id: 'c-main',
        title: 'Main',
        target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
        params: { temperature: 0.2, max_tokens: 1024 },
        fallback_channels: [],
        capabilities: { tools: true, json: true },
      },
      {
        id: 'c-fallback',
        title: 'Fallback',
        target: { provider: 'azure', mode: 'chat', model: 'gpt-4o-mini' },
        params: { temperature: 0.1, max_tokens: 512 },
        fallback_channels: [],
        capabilities: { tools: true, json: false },
      },
    ],
    rules: [
      {
        id: 'rule-disabled',
        priority: 999,
        enabled: false,
        match: { roles: [], skills: [], kinds: [] },
        route: { channel_id: 'c-fallback' },
      },
      {
        id: 'rule-main',
        priority: 100,
        enabled: true,
        match: { roles: ['teacher'], skills: [], kinds: [] },
        route: { channel_id: 'c-main' },
      },
    ],
  },
  validation: { errors: validationErrors, warnings: [] },
  proposals: [
    {
      proposal_id: 'p-1',
      created_at: '2026-02-14T11:00:00Z',
      created_by: 'teacher-admin',
      status: 'pending',
      note: 'pending change',
      validation_ok: true,
      proposal_path: '/tmp/p-1.json',
    },
    {
      proposal_id: 'p-2',
      created_at: '2026-02-14T10:00:00Z',
      created_by: 'teacher-admin',
      status: 'approved',
      note: 'done',
      validation_ok: true,
      proposal_path: '/tmp/p-2.json',
    },
  ],
  history: [
    {
      file: 'v12.json',
      version: 12,
      saved_at: '2026-02-14T12:00:00Z',
      saved_by: 'teacher-admin',
      source: 'ui',
      note: 'latest',
      summary: summary(),
    },
    {
      file: 'v11.json',
      version: 11,
      saved_at: '2026-02-14T10:00:00Z',
      saved_by: 'teacher-admin',
      source: 'ui',
      note: 'previous',
      summary: summary({ primary_model: 'gpt-4.1', top_rule_id: 'rule-old' }),
    },
  ],
  catalog: {
    providers: [],
    defaults: { provider: 'openai', mode: 'openai-chat' },
    fallback_chain: [],
  },
})

describe('useRoutingDerivedState', () => {
  it('derives live rule/channel and pending proposals', () => {
    const { result } = renderHook(() =>
      useRoutingDerivedState({
        overview: overviewFixture(),
        hasLocalEdits: false,
      }),
    )

    expect(result.current.pendingProposals).toHaveLength(1)
    expect(result.current.livePrimaryRule?.id).toBe('rule-main')
    expect(result.current.livePrimaryChannel?.id).toBe('c-main')
    expect(result.current.liveStatusTone).toBe('ok')
    expect(result.current.liveStatusText).toBe('已生效')
    expect(result.current.historyRows[0]?.changes).toContain('模型切换：gpt-4.1 → gpt-4.1-mini')
  })

  it('switches status tone/text for local edits and validation errors', () => {
    const { result: editedResult } = renderHook(() =>
      useRoutingDerivedState({
        overview: overviewFixture(),
        hasLocalEdits: true,
      }),
    )
    expect(editedResult.current.liveStatusTone).toBe('warn')
    expect(editedResult.current.liveStatusText).toBe('草稿未生效')

    const { result: invalidResult } = renderHook(() =>
      useRoutingDerivedState({
        overview: overviewFixture(['schema invalid']),
        hasLocalEdits: true,
      }),
    )
    expect(invalidResult.current.liveStatusTone).toBe('danger')
    expect(invalidResult.current.liveStatusText).toBe('配置异常')
  })
})
