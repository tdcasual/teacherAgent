import { describe, expect, it } from 'vitest'
import type { RoutingHistoryItem, RoutingHistorySummary } from './routingTypes'
import { buildHistoryChangeSummary, deriveHistorySummary } from './routingHistoryUtils'

const baseItem = (overrides?: Partial<RoutingHistoryItem>): RoutingHistoryItem => ({
  file: 'routing-v1.json',
  version: 1,
  saved_at: '2026-02-14T10:00:00Z',
  saved_by: 'teacher-admin',
  source: 'ui',
  note: '',
  ...overrides,
})

describe('routingHistoryUtils', () => {
  it('prefers embedded summary when present', () => {
    const embedded: RoutingHistorySummary = {
      enabled: true,
      channel_count: 1,
      rule_count: 1,
      primary_channel_id: 'primary',
      primary_channel_title: 'Primary',
      primary_provider: 'openai',
      primary_mode: 'openai-chat',
      primary_model: 'gpt-4.1-mini',
      top_rule_id: 'rule_primary',
    }

    const summary = deriveHistorySummary(baseItem({ summary: embedded }))
    expect(summary).toBe(embedded)
  })

  it('derives summary from config payload when summary is missing', () => {
    const summary = deriveHistorySummary(
      baseItem({
        config: {
          enabled: true,
          channels: [
            {
              id: 'primary',
              title: 'Primary channel',
              target: { provider: 'openai', mode: 'openai-chat', model: 'gpt-4.1-mini' },
            },
          ],
          rules: [
            { id: 'rule_low', priority: 10 },
            { id: 'rule_high', priority: 100 },
          ],
        },
      }),
    )

    expect(summary).toEqual({
      enabled: true,
      channel_count: 1,
      rule_count: 2,
      primary_channel_id: 'primary',
      primary_channel_title: 'Primary channel',
      primary_provider: 'openai',
      primary_mode: 'openai-chat',
      primary_model: 'gpt-4.1-mini',
      top_rule_id: 'rule_high',
    })
  })

  it('returns baseline message when previous summary is absent', () => {
    const current: RoutingHistorySummary = {
      enabled: true,
      channel_count: 2,
      rule_count: 3,
      primary_channel_id: 'primary',
      primary_channel_title: 'Primary',
      primary_provider: 'openai',
      primary_mode: 'openai-chat',
      primary_model: 'gpt-4.1-mini',
      top_rule_id: 'rule_primary',
    }

    expect(buildHistoryChangeSummary(current, null)).toEqual(['首个保留版本，暂无可对比基线。'])
  })

  it('describes concrete field changes between two summaries', () => {
    const previous: RoutingHistorySummary = {
      enabled: true,
      channel_count: 1,
      rule_count: 1,
      primary_channel_id: 'primary',
      primary_channel_title: 'Primary',
      primary_provider: 'openai',
      primary_mode: 'openai-chat',
      primary_model: 'gpt-4.1-mini',
      top_rule_id: 'rule_primary',
    }
    const current: RoutingHistorySummary = {
      ...previous,
      enabled: false,
      channel_count: 3,
      rule_count: 4,
      primary_channel_id: 'fallback',
      primary_model: 'gpt-4.1',
      top_rule_id: 'rule_fallback',
    }

    const changes = buildHistoryChangeSummary(current, previous)
    expect(changes).toContain('模型切换：gpt-4.1-mini → gpt-4.1')
    expect(changes).toContain('主渠道变更：primary → fallback')
    expect(changes).toContain('主规则变更：rule_primary → rule_fallback')
    expect(changes).toContain('规则数量：1 → 4')
    expect(changes).toContain('渠道数量：1 → 3')
    expect(changes).toContain('路由状态：启用 → 关闭')
  })

  it('returns no-structural-change message when summaries are equivalent', () => {
    const summary: RoutingHistorySummary = {
      enabled: true,
      channel_count: 2,
      rule_count: 3,
      primary_channel_id: 'primary',
      primary_channel_title: 'Primary',
      primary_provider: 'openai',
      primary_mode: 'openai-chat',
      primary_model: 'gpt-4.1-mini',
      top_rule_id: 'rule_primary',
    }

    expect(buildHistoryChangeSummary(summary, { ...summary })).toEqual(['路由结构未变化，主要为备注或时间更新。'])
  })
})
