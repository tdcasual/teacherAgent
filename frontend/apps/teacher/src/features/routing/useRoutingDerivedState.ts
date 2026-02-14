import { useMemo } from 'react'
import { buildHistoryChangeSummary, deriveHistorySummary } from './routingHistoryUtils'
import type { RoutingOverview } from './routingTypes'

type Props = {
  overview: RoutingOverview | null
  hasLocalEdits: boolean
}

export function useRoutingDerivedState({ overview, hasLocalEdits }: Props) {
  const pendingProposals = useMemo(
    () => (overview?.proposals || []).filter((item) => item.status === 'pending'),
    [overview?.proposals],
  )
  const history = useMemo(() => overview?.history || [], [overview?.history])

  const liveRouting = overview?.routing || null
  const liveEnabledRules = useMemo(
    () =>
      [...(liveRouting?.rules || [])]
        .filter((rule) => rule.enabled !== false)
        .sort((left, right) => (right.priority || 0) - (left.priority || 0)),
    [liveRouting?.rules],
  )
  const livePrimaryRule = liveEnabledRules[0] || null
  const livePrimaryChannel = useMemo(() => {
    const channels = liveRouting?.channels || []
    const routedChannelId = livePrimaryRule?.route?.channel_id || ''
    if (routedChannelId) {
      const matched = channels.find((channel) => channel.id === routedChannelId)
      if (matched) return matched
    }
    return channels[0] || null
  }, [livePrimaryRule?.route?.channel_id, liveRouting?.channels])

  const liveStatusText = overview?.validation?.errors?.length
    ? '配置异常'
    : hasLocalEdits
      ? '草稿未生效'
      : '已生效'
  const liveStatusTone: 'danger' | 'warn' | 'ok' = overview?.validation?.errors?.length
    ? 'danger'
    : hasLocalEdits
      ? 'warn'
      : 'ok'

  const historyRows = useMemo(
    () =>
      history.map((item, index) => {
        const currentSummary = deriveHistorySummary(item)
        const previousSummary = history[index + 1] ? deriveHistorySummary(history[index + 1]) : null
        return {
          item,
          summary: currentSummary,
          changes: buildHistoryChangeSummary(currentSummary, previousSummary),
        }
      }),
    [history],
  )

  return {
    pendingProposals,
    history,
    liveRouting,
    livePrimaryRule,
    livePrimaryChannel,
    liveStatusText,
    liveStatusTone,
    historyRows,
  }
}
