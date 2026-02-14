import { useCallback } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { emptyRoutingConfig } from './routingTypes'
import type {
  RoutingCatalogProvider,
  RoutingChannel,
  RoutingConfig,
  RoutingOverview,
  RoutingRule,
} from './routingTypes'

const makeId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`

type Props = {
  teacherId: string
  hasLocalEdits: boolean
  draft: RoutingConfig
  overview: RoutingOverview | null
  providers: RoutingCatalogProvider[]
  providerModeMap: Map<string, string[]>
  cloneConfig: (config: RoutingConfig) => RoutingConfig
  setTeacherId: Dispatch<SetStateAction<string>>
  setDraft: Dispatch<SetStateAction<RoutingConfig>>
  setHasLocalEdits: Dispatch<SetStateAction<boolean>>
  setStatus: Dispatch<SetStateAction<string>>
  setError: Dispatch<SetStateAction<string>>
}

export function useRoutingDraftActions({
  teacherId,
  hasLocalEdits,
  draft,
  overview,
  providers,
  providerModeMap,
  cloneConfig,
  setTeacherId,
  setDraft,
  setHasLocalEdits,
  setStatus,
  setError,
}: Props) {
  const setDraftWithEdit = useCallback((updater: (prev: RoutingConfig) => RoutingConfig) => {
    setDraft((prev) => updater(prev))
    setHasLocalEdits(true)
  }, [setDraft, setHasLocalEdits])

  const handleTeacherIdChange = useCallback((value: string) => {
    if (value === teacherId) return
    if (hasLocalEdits && typeof window !== 'undefined') {
      const confirmed = window.confirm('切换教师标识会丢弃当前本地草稿，是否继续？')
      if (!confirmed) return
    }
    setTeacherId(value)
    setHasLocalEdits(false)
    setStatus('')
    setError('')
  }, [teacherId, hasLocalEdits, setTeacherId, setHasLocalEdits, setStatus, setError])

  const addChannel = useCallback(() => {
    const defaultProvider = overview?.catalog?.defaults?.provider || providers[0]?.provider || 'siliconflow'
    const defaultModes = providerModeMap.get(defaultProvider) || []
    const defaultMode = overview?.catalog?.defaults?.mode || defaultModes[0] || 'openai-chat'
    const channel: RoutingChannel = {
      id: makeId('channel'),
      title: '新渠道',
      target: {
        provider: defaultProvider,
        mode: defaultMode,
        model: '',
      },
      params: { temperature: null, max_tokens: null },
      fallback_channels: [],
      capabilities: { tools: true, json: true },
    }
    setDraftWithEdit((prev) => ({ ...prev, channels: [...prev.channels, channel] }))
  }, [overview?.catalog?.defaults?.mode, overview?.catalog?.defaults?.provider, providerModeMap, providers, setDraftWithEdit])

  const removeChannel = useCallback((index: number) => {
    setDraftWithEdit((prev) => {
      const removed = prev.channels[index]
      const nextChannels = prev.channels.filter((_, channelIndex) => channelIndex !== index)
      const fallbackChannelId = nextChannels[0]?.id || ''
      const nextRules = prev.rules.map((rule) => {
        if ((rule.route?.channel_id || '') !== (removed?.id || '')) return rule
        return { ...rule, route: { channel_id: fallbackChannelId } }
      })
      return { ...prev, channels: nextChannels, rules: nextRules }
    })
  }, [setDraftWithEdit])

  const updateChannel = useCallback((index: number, updater: (channel: RoutingChannel) => RoutingChannel) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      channels: prev.channels.map((channel, channelIndex) => (channelIndex === index ? updater(channel) : channel)),
    }))
  }, [setDraftWithEdit])

  const addRule = useCallback(() => {
    const firstChannelId = draft.channels[0]?.id || ''
    const rule: RoutingRule = {
      id: makeId('rule'),
      priority: 100,
      enabled: true,
      match: { roles: ['teacher'], skills: [], kinds: [], needs_tools: undefined, needs_json: undefined },
      route: { channel_id: firstChannelId },
    }
    setDraftWithEdit((prev) => ({ ...prev, rules: [...prev.rules, rule] }))
  }, [draft.channels, setDraftWithEdit])

  const removeRule = useCallback((index: number) => {
    setDraftWithEdit((prev) => ({ ...prev, rules: prev.rules.filter((_, ruleIndex) => ruleIndex !== index) }))
  }, [setDraftWithEdit])

  const updateRule = useCallback((index: number, updater: (rule: RoutingRule) => RoutingRule) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      rules: prev.rules.map((rule, ruleIndex) => (ruleIndex === index ? updater(rule) : rule)),
    }))
  }, [setDraftWithEdit])

  const handleResetDraft = useCallback(() => {
    if (!overview) return
    setDraft(cloneConfig(overview.routing || emptyRoutingConfig()))
    setHasLocalEdits(false)
    setStatus('已恢复为线上配置。')
    setError('')
  }, [overview, setDraft, cloneConfig, setHasLocalEdits, setStatus, setError])

  return {
    setDraftWithEdit,
    handleTeacherIdChange,
    addChannel,
    removeChannel,
    updateChannel,
    addRule,
    removeRule,
    updateRule,
    handleResetDraft,
  }
}
