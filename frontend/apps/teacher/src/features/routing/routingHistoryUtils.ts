import type { RoutingHistoryItem, RoutingHistorySummary } from './routingTypes'

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

const asPriority = (value: unknown) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

export const deriveHistorySummary = (item: RoutingHistoryItem): RoutingHistorySummary | null => {
  if (item.summary) return item.summary
  const config = asRecord(item.config)
  if (!config) return null

  const channels = (Array.isArray(config.channels) ? config.channels : [])
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))
  const rules = (Array.isArray(config.rules) ? config.rules : [])
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))

  const primaryChannel = channels[0] || null
  const primaryTarget = asRecord(primaryChannel?.target) || {}
  const topRule = [...rules].sort((left, right) => asPriority(right.priority) - asPriority(left.priority))[0] || null

  return {
    enabled: Boolean(config.enabled),
    channel_count: channels.length,
    rule_count: rules.length,
    primary_channel_id: String(primaryChannel?.id || ''),
    primary_channel_title: String(primaryChannel?.title || ''),
    primary_provider: String(primaryTarget.provider || ''),
    primary_mode: String(primaryTarget.mode || ''),
    primary_model: String(primaryTarget.model || ''),
    top_rule_id: String(topRule?.id || ''),
  }
}

export const buildHistoryChangeSummary = (current: RoutingHistorySummary | null, previous: RoutingHistorySummary | null) => {
  if (!current) return ['无结构化变更数据，请查看配置 JSON。']
  if (!previous) return ['首个保留版本，暂无可对比基线。']

  const changes: string[] = []
  if (current.primary_model !== previous.primary_model) {
    changes.push(`模型切换：${previous.primary_model || '未配置'} → ${current.primary_model || '未配置'}`)
  }
  if (current.primary_channel_id !== previous.primary_channel_id) {
    changes.push(`主渠道变更：${previous.primary_channel_id || '未配置'} → ${current.primary_channel_id || '未配置'}`)
  }
  if (current.top_rule_id !== previous.top_rule_id) {
    changes.push(`主规则变更：${previous.top_rule_id || '未配置'} → ${current.top_rule_id || '未配置'}`)
  }
  if (current.rule_count !== previous.rule_count) {
    changes.push(`规则数量：${previous.rule_count} → ${current.rule_count}`)
  }
  if (current.channel_count !== previous.channel_count) {
    changes.push(`渠道数量：${previous.channel_count} → ${current.channel_count}`)
  }
  if (current.enabled !== previous.enabled) {
    changes.push(`路由状态：${previous.enabled ? '启用' : '关闭'} → ${current.enabled ? '启用' : '关闭'}`)
  }
  if (!changes.length) changes.push('路由结构未变化，主要为备注或时间更新。')
  return changes
}
