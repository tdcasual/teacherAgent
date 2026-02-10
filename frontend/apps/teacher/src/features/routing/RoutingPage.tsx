import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  createProviderRegistryItem,
  createRoutingProposal,
  deleteProviderRegistryItem,
  fetchProviderRegistry,
  fetchRoutingProposalDetail,
  fetchRoutingOverview,
  probeProviderRegistryModels,
  reviewRoutingProposal,
  rollbackRoutingConfig,
  simulateRouting,
  updateProviderRegistryItem,
} from './routingApi'
import { useProviderModels } from './useProviderModels'
import ModelCombobox from './ModelCombobox'
import type {
  RoutingCatalogProvider,
  RoutingChannel,
  RoutingConfig,
  RoutingHistoryItem,
  RoutingHistorySummary,
  RoutingOverview,
  TeacherProviderRegistryOverview,
  RoutingProposalDetail,
  RoutingRule,
  RoutingSimulateResult,
} from './routingTypes'
import { emptyRoutingConfig } from './routingTypes'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../utils/storage'

export type RoutingSection = 'general' | 'providers' | 'channels' | 'rules' | 'simulate' | 'history'

type Props = {
  apiBase: string
  onApiBaseChange?: (value: string) => void
  onDirtyChange?: (dirty: boolean) => void
  /** When provided, only render this section (no tab bar, no page chrome) */
  section?: RoutingSection
}

const makeId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`

const parseList = (value: string) =>
  value
    .split(/[，,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const formatList = (items: string[]) => items.join('，')

const asNumberOrNull = (value: string): number | null => {
  const text = value.trim()
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

const cloneConfig = (config: RoutingConfig): RoutingConfig => ({
  schema_version: config.schema_version,
  enabled: Boolean(config.enabled),
  version: Number(config.version || 1),
  updated_at: config.updated_at || '',
  updated_by: config.updated_by || '',
  channels: (config.channels || []).map((channel) => ({
    id: channel.id || '',
    title: channel.title || '',
    target: {
      provider: channel.target?.provider || '',
      mode: channel.target?.mode || '',
      model: channel.target?.model || '',
    },
    params: {
      temperature: channel.params?.temperature ?? null,
      max_tokens: channel.params?.max_tokens ?? null,
    },
    fallback_channels: Array.isArray(channel.fallback_channels) ? [...channel.fallback_channels] : [],
    capabilities: {
      tools: channel.capabilities?.tools ?? true,
      json: channel.capabilities?.json ?? true,
    },
  })),
  rules: (config.rules || []).map((rule) => ({
    id: rule.id || '',
    priority: Number(rule.priority || 0),
    enabled: rule.enabled !== false,
    match: {
      roles: Array.isArray(rule.match?.roles) ? [...rule.match.roles] : [],
      skills: Array.isArray(rule.match?.skills) ? [...rule.match.skills] : [],
      kinds: Array.isArray(rule.match?.kinds) ? [...rule.match.kinds] : [],
      needs_tools: rule.match?.needs_tools ?? undefined,
      needs_json: rule.match?.needs_json ?? undefined,
    },
    route: { channel_id: rule.route?.channel_id || '' },
  })),
})

const boolMatchValue = (value: boolean | null | undefined) => {
  if (value === true) return 'true'
  if (value === false) return 'false'
  return 'any'
}

const boolMatchFromValue = (value: string): boolean | undefined => {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

const formatTargetLabel = (provider?: string, mode?: string, model?: string) => {
  const text = [provider || '', mode || '', model || ''].map((item) => item.trim()).filter(Boolean).join(' / ')
  return text || '未配置'
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

const asPriority = (value: unknown) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const deriveHistorySummary = (item: RoutingHistoryItem): RoutingHistorySummary | null => {
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

const buildHistoryChangeSummary = (current: RoutingHistorySummary | null, previous: RoutingHistorySummary | null) => {
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

export default function RoutingPage({ apiBase, onApiBaseChange, onDirtyChange, section }: Props) {
  const activeTab = section || 'general'
  const [teacherId, setTeacherId] = useState(() => {
    return safeLocalStorageGetItem('teacherRoutingTeacherId') || ''
  })
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [overview, setOverview] = useState<RoutingOverview | null>(null)
  const [draft, setDraft] = useState<RoutingConfig>(() => emptyRoutingConfig())
  const [hasLocalEdits, setHasLocalEdits] = useState(false)
  const [proposalNote, setProposalNote] = useState('')
  const [rollbackVersion, setRollbackVersion] = useState('')
  const [rollbackNote, setRollbackNote] = useState('')
  const [simRole, setSimRole] = useState('teacher')
  const [simSkillId, setSimSkillId] = useState('physics-teacher-ops')
  const [simKind, setSimKind] = useState('chat.agent')
  const [simNeedsTools, setSimNeedsTools] = useState(true)
  const [simNeedsJson, setSimNeedsJson] = useState(false)
  const [simResult, setSimResult] = useState<RoutingSimulateResult | null>(null)
  const [expandedProposalIds, setExpandedProposalIds] = useState<Record<string, boolean>>({})
  const [proposalDetails, setProposalDetails] = useState<Record<string, RoutingProposalDetail>>({})
  const [proposalLoadingMap, setProposalLoadingMap] = useState<Record<string, boolean>>({})
  const [showManualReview, setShowManualReview] = useState(() => safeLocalStorageGetItem('teacherRoutingManualReview') === '1')
  const [showHistoryVersions, setShowHistoryVersions] = useState(() => safeLocalStorageGetItem('teacherRoutingHistoryExpanded') === '1')
  const [providerOverview, setProviderOverview] = useState<TeacherProviderRegistryOverview | null>(null)
  const [providerBusy, setProviderBusy] = useState(false)
  const [providerProbeMap, setProviderProbeMap] = useState<Record<string, string>>({})
  const [providerCreateForm, setProviderCreateForm] = useState({
    provider_id: '',
    display_name: '',
    base_url: '',
    api_key: '',
    enabled: true,
  })
  const [providerEditMap, setProviderEditMap] = useState<
    Record<string, { display_name: string; base_url: string; enabled: boolean; api_key: string }>
  >({})
  const [providerAddMode, setProviderAddMode] = useState<'' | 'preset' | 'custom'>('')
  const [providerAddPreset, setProviderAddPreset] = useState('')
  const hasLocalEditsRef = useRef(false)

  const { modelsMap, fetchModels } = useProviderModels(apiBase, teacherId)

  useEffect(() => {
    onDirtyChange?.(hasLocalEdits)
  }, [hasLocalEdits, onDirtyChange])

  useEffect(() => {
    hasLocalEditsRef.current = hasLocalEdits
  }, [hasLocalEdits])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingTeacherId', teacherId)
  }, [teacherId])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingManualReview', showManualReview ? '1' : '0')
  }, [showManualReview])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingHistoryExpanded', showHistoryVersions ? '1' : '0')
  }, [showHistoryVersions])

  useEffect(() => {
    setExpandedProposalIds({})
    setProposalDetails({})
    setProposalLoadingMap({})
  }, [teacherId])

  const loadOverview = useCallback(
    async (options?: { silent?: boolean; forceReplaceDraft?: boolean }) => {
      const silent = Boolean(options?.silent)
      const forceReplaceDraft = Boolean(options?.forceReplaceDraft)
      if (!silent) setLoading(true)
      setError('')
      try {
        let nextError = ''
        let routingLoaded = false

        try {
          const data = await fetchRoutingOverview(apiBase, {
            teacher_id: teacherId || undefined,
            history_limit: 40,
            proposal_limit: 40,
          })
          routingLoaded = true
          setOverview(data)
          if (forceReplaceDraft || !hasLocalEditsRef.current) {
            setDraft(cloneConfig(data.routing || emptyRoutingConfig()))
            setHasLocalEdits(false)
          }
        } catch (err) {
          nextError = (err as Error).message || '加载模型路由失败'
        }

        try {
          const providerData = await fetchProviderRegistry(apiBase, { teacher_id: teacherId || undefined })
          setProviderOverview(providerData)
        } catch (err) {
          const providerError = (err as Error).message || '加载 Provider 配置失败'
          nextError = nextError ? `${nextError}；${providerError}` : providerError
        }

        if (nextError) setError(nextError)
      } catch (err) {
        setError((err as Error).message || '加载模型路由失败')
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [apiBase, teacherId],
  )

  useEffect(() => {
    void loadOverview({ forceReplaceDraft: true })
  }, [loadOverview])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadOverview({ silent: true })
    }, 30000)
    return () => window.clearInterval(timer)
  }, [loadOverview])

  useEffect(() => {
    const next: Record<string, { display_name: string; base_url: string; enabled: boolean; api_key: string }> = {}
    ;(providerOverview?.providers || []).forEach((item) => {
      next[item.provider] = {
        display_name: item.display_name || '',
        base_url: item.base_url || '',
        enabled: item.enabled !== false,
        api_key: '',
      }
    })
    setProviderEditMap(next)
  }, [providerOverview?.providers])

  const providers = useMemo(() => (overview?.catalog?.providers || []) as RoutingCatalogProvider[], [overview?.catalog?.providers])
  const providerModeMap = useMemo(() => {
    const map = new Map<string, string[]>()
    providers.forEach((provider) => {
      map.set(
        provider.provider,
        (provider.modes || []).map((mode) => mode.mode).filter(Boolean),
      )
    })
    return map
  }, [providers])

  // Auto-probe models when channels tab is active (only configured providers)
  useEffect(() => {
    if (activeTab !== 'channels') return
    const configuredProviders = new Set(
      (providerOverview?.providers || []).map((p) => p.provider),
    )
    const seen = new Set<string>()
    for (const ch of draft.channels) {
      const p = ch.target?.provider
      if (p && !seen.has(p) && configuredProviders.has(p)) {
        seen.add(p)
        void fetchModels(p)
      }
    }
  }, [activeTab]) // eslint-disable-line react-hooks/exhaustive-deps

  const setDraftWithEdit = useCallback((updater: (prev: RoutingConfig) => RoutingConfig) => {
    setDraft((prev) => updater(prev))
    setHasLocalEdits(true)
  }, [])

  const handleTeacherIdChange = (value: string) => {
    if (value === teacherId) return
    if (hasLocalEdits && typeof window !== 'undefined') {
      const confirmed = window.confirm('切换教师标识会丢弃当前本地草稿，是否继续？')
      if (!confirmed) return
    }
    setTeacherId(value)
    setHasLocalEdits(false)
    setStatus('')
    setError('')
  }

  const addChannel = () => {
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
  }

  const removeChannel = (index: number) => {
    setDraftWithEdit((prev) => {
      const removed = prev.channels[index]
      const nextChannels = prev.channels.filter((_, i) => i !== index)
      const fallbackChannelId = nextChannels[0]?.id || ''
      const nextRules = prev.rules.map((rule) => {
        if ((rule.route?.channel_id || '') !== (removed?.id || '')) return rule
        return { ...rule, route: { channel_id: fallbackChannelId } }
      })
      return { ...prev, channels: nextChannels, rules: nextRules }
    })
  }

  const updateChannel = (index: number, updater: (channel: RoutingChannel) => RoutingChannel) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      channels: prev.channels.map((channel, idx) => (idx === index ? updater(channel) : channel)),
    }))
  }

  const addRule = () => {
    const firstChannelId = draft.channels[0]?.id || ''
    const rule: RoutingRule = {
      id: makeId('rule'),
      priority: 100,
      enabled: true,
      match: { roles: ['teacher'], skills: [], kinds: [], needs_tools: undefined, needs_json: undefined },
      route: { channel_id: firstChannelId },
    }
    setDraftWithEdit((prev) => ({ ...prev, rules: [...prev.rules, rule] }))
  }

  const removeRule = (index: number) => {
    setDraftWithEdit((prev) => ({ ...prev, rules: prev.rules.filter((_, idx) => idx !== index) }))
  }

  const updateRule = (index: number, updater: (rule: RoutingRule) => RoutingRule) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      rules: prev.rules.map((rule, idx) => (idx === index ? updater(rule) : rule)),
    }))
  }

  const handleCreateProvider = async () => {
    const formBaseUrl = providerCreateForm.base_url.trim()
    const formApiKey = providerCreateForm.api_key.trim()
    // For preset providers, base_url is optional (use catalog default)
    const catalogProvider = (providerOverview?.shared_catalog?.providers || []).find(
      (p) => p.provider === providerCreateForm.provider_id.trim(),
    )
    const effectiveBaseUrl = formBaseUrl || catalogProvider?.base_url || ''
    if (!effectiveBaseUrl || !formApiKey) {
      setError('新增 Provider 需要填写 base_url 和 api_key')
      return
    }
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await createProviderRegistryItem(apiBase, {
        teacher_id: teacherId || undefined,
        provider_id: providerCreateForm.provider_id.trim() || undefined,
        display_name: providerCreateForm.display_name.trim() || undefined,
        base_url: effectiveBaseUrl,
        api_key: formApiKey,
        enabled: providerCreateForm.enabled,
      })
      if (!result.ok) throw new Error(result.error ? String(result.error) : '新增失败')
      setProviderCreateForm({
        provider_id: '',
        display_name: '',
        base_url: '',
        api_key: '',
        enabled: true,
      })
      setProviderAddMode('')
      setProviderAddPreset('')
      setStatus('Provider 已新增并即时生效。')
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '新增 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }

  const handleUpdateProvider = async (providerId: string) => {
    const draftForm = providerEditMap[providerId]
    if (!draftForm) return
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const payload: {
        teacher_id?: string
        display_name?: string
        base_url?: string
        enabled?: boolean
        api_key?: string
      } = {
        teacher_id: teacherId || undefined,
        display_name: draftForm.display_name.trim() || undefined,
        enabled: Boolean(draftForm.enabled),
      }
      payload.base_url = draftForm.base_url.trim()
      if (draftForm.api_key.trim()) payload.api_key = draftForm.api_key.trim()
      const result = await updateProviderRegistryItem(apiBase, providerId, payload)
      if (!result.ok) throw new Error(result.error ? String(result.error) : '更新失败')
      setStatus(`Provider ${providerId} 已更新。`)
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '更新 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }

  const handleDisableProvider = async (providerId: string) => {
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await deleteProviderRegistryItem(apiBase, providerId, { teacher_id: teacherId || undefined })
      if (!result.ok) throw new Error(result.error ? String(result.error) : '禁用失败')
      setStatus(`Provider ${providerId} 已禁用。`)
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '禁用 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }

  const handleProbeProviderModels = async (providerId: string) => {
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await probeProviderRegistryModels(apiBase, providerId, { teacher_id: teacherId || undefined })
      if (!result.ok) throw new Error(result.detail || result.error || '探测失败')
      const models = (result.models || []).slice(0, 12)
      setProviderProbeMap((prev) => ({ ...prev, [providerId]: models.join('，') || '未返回模型列表' }))
      setStatus(`Provider ${providerId} 探测完成。`)
    } catch (err) {
      setError((err as Error).message || '探测模型失败')
    } finally {
      setProviderBusy(false)
    }
  }

  const handleResetDraft = () => {
    if (!overview) return
    setDraft(cloneConfig(overview.routing || emptyRoutingConfig()))
    setHasLocalEdits(false)
    setStatus('已恢复为线上配置。')
    setError('')
  }

  const handleSimulate = async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await simulateRouting(apiBase, {
        teacher_id: teacherId || undefined,
        role: simRole || undefined,
        skill_id: simSkillId || undefined,
        kind: simKind || undefined,
        needs_tools: simNeedsTools,
        needs_json: simNeedsJson,
        config: draft as unknown as Record<string, unknown>,
      })
      setSimResult(result)
      setStatus('仿真完成。')
    } catch (err) {
      setError((err as Error).message || '仿真失败')
    } finally {
      setBusy(false)
    }
  }

  const handlePropose = async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const created = await createRoutingProposal(apiBase, {
        teacher_id: teacherId || undefined,
        note: proposalNote || undefined,
        config: draft as unknown as Record<string, unknown>,
      })
      if (!created.ok) throw new Error(created.error ? JSON.stringify(created.error) : '提案创建失败')

      const proposalId = String(created.proposal_id || '').trim()
      if (!proposalId) throw new Error('提案创建成功但未返回 proposal_id')

      const applied = await reviewRoutingProposal(apiBase, proposalId, {
        teacher_id: teacherId || undefined,
        approve: true,
      })
      if (!applied.ok) throw new Error(applied.error ? JSON.stringify(applied.error) : '自动生效失败')

      const nextVersion = Number(applied.version || 0)
      const versionText = Number.isFinite(nextVersion) && nextVersion > 0 ? `v${nextVersion}` : '最新版本'
      setStatus(`配置已生效（${versionText}）`)
      setProposalNote('')
      setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: false }))
      await loadOverview({ silent: true, forceReplaceDraft: true })
    } catch (err) {
      setError((err as Error).message || '保存并生效失败')
    } finally {
      setBusy(false)
    }
  }

  const handleReviewProposal = async (proposalId: string, approve: boolean) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await reviewRoutingProposal(apiBase, proposalId, {
        teacher_id: teacherId || undefined,
        approve,
      })
      if (!result.ok) throw new Error(result.error ? JSON.stringify(result.error) : '审核失败')
      setStatus(approve ? `提案 ${proposalId} 已生效` : `提案 ${proposalId} 已拒绝`)
      setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: false }))
      await loadOverview({ silent: true, forceReplaceDraft: approve })
    } catch (err) {
      setError((err as Error).message || '提案审核失败')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleProposalDetail = async (proposalId: string) => {
    const nextExpanded = !Boolean(expandedProposalIds[proposalId])
    setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: nextExpanded }))
    if (!nextExpanded) return
    if (proposalDetails[proposalId] || proposalLoadingMap[proposalId]) return
    setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: true }))
    setError('')
    try {
      const detail = await fetchRoutingProposalDetail(apiBase, proposalId, teacherId || undefined)
      setProposalDetails((prev) => ({ ...prev, [proposalId]: detail }))
    } catch (err) {
      setError((err as Error).message || '提案详情加载失败')
    } finally {
      setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: false }))
    }
  }

  const handleRollback = async (targetVersion: number) => {
    if (!Number.isFinite(targetVersion) || targetVersion <= 0) {
      setError('回滚版本号无效')
      return
    }
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await rollbackRoutingConfig(apiBase, {
        teacher_id: teacherId || undefined,
        target_version: targetVersion,
        note: rollbackNote || undefined,
      })
      if (!result.ok) throw new Error(result.error || '回滚失败')
      setStatus(`已回滚到版本 ${targetVersion}`)
      setRollbackVersion('')
      setRollbackNote('')
      await loadOverview({ silent: true, forceReplaceDraft: true })
    } catch (err) {
      setError((err as Error).message || '回滚失败')
    } finally {
      setBusy(false)
    }
  }

  const pendingProposals = (overview?.proposals || []).filter((item) => item.status === 'pending')
  const history = overview?.history || []

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
  const liveStatusTone = overview?.validation?.errors?.length ? 'danger' : hasLocalEdits ? 'warn' : 'ok'

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

  const simCandidates = simResult?.decision?.candidates || []
  const simPrimaryCandidate = simCandidates[0] || null

  const ruleOrderHint = draft.rules
    .slice()
    .sort((a, b) => (b.priority || 0) - (a.priority || 0))
    .map((rule) => `${rule.id || '未命名'}(${rule.priority})`)
    .join(' -> ')

  return (
    <div className="routing-page">
      {status && <div className="status ok">{status}</div>}
      {error && <div className="status err">{error}</div>}

      <div className="routing-current-card">
        <div className="routing-current-header">
          <div className="routing-current-title-wrap">
            <h3>当前生效配置</h3>
            <span className="routing-current-subtitle">先看结论：当前实际生效的规则、渠道与模型</span>
          </div>
          <span className={`routing-chip routing-chip-${liveStatusTone}`}>{loading ? '加载中' : liveStatusText}</span>
        </div>
        <div className="routing-current-grid">
          <div className="routing-current-item">
            <span>生效规则</span>
            <strong>{livePrimaryRule?.id || '默认回退'}</strong>
          </div>
          <div className="routing-current-item">
            <span>主渠道</span>
            <strong>{livePrimaryChannel?.title || livePrimaryChannel?.id || '未配置'}</strong>
          </div>
          <div className="routing-current-item">
            <span>目标模型</span>
            <strong>
              {formatTargetLabel(
                livePrimaryChannel?.target?.provider,
                livePrimaryChannel?.target?.mode,
                livePrimaryChannel?.target?.model,
              )}
            </strong>
          </div>
          <div className="routing-current-item">
            <span>版本 / 更新时间</span>
            <strong>
              v{liveRouting?.version || '-'} / {liveRouting?.updated_at || '—'}
            </strong>
          </div>
        </div>
      </div>

      {activeTab === 'general' && (
        <div className="settings-section">
          <div className="routing-meta-grid">
            <div className="routing-field">
              <label>API Base</label>
              <input
                value={apiBase}
                onChange={(e) => onApiBaseChange?.(e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>
            <div className="routing-field">
              <label>教师标识（可选）</label>
              <input value={teacherId} onChange={(e) => handleTeacherIdChange(e.target.value)} placeholder="默认 teacher" />
            </div>
            <div className="routing-field">
              <label>启用自定义路由</label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={Boolean(draft.enabled)}
                  onChange={(e) => setDraftWithEdit((prev) => ({ ...prev, enabled: e.target.checked }))}
                />
                {draft.enabled ? '已启用' : '已关闭'}
              </label>
            </div>
          </div>
          <div className="routing-stats-row">
            <span>线上版本：{overview?.routing?.version ?? '-'}</span>
            <span>草稿规则：{draft.rules.length} 条</span>
            <span>草稿渠道：{draft.channels.length} 个</span>
            <span>最后更新：{overview?.routing?.updated_at || '—'}</span>
          </div>
          {hasLocalEdits && <div className="status ok">当前为本地草稿，尚未保存生效。</div>}
          {overview?.validation?.errors?.length ? (
            <div className="status err">线上配置校验错误：{overview.validation.errors.join('；')}</div>
          ) : null}
          {overview?.validation?.warnings?.length ? (
            <div className="status ok">线上配置提示：{overview.validation.warnings.join('；')}</div>
          ) : null}
          <div className="routing-actions">
            <button type="button" className="secondary-btn" onClick={() => void loadOverview()} disabled={loading || busy}>
              {loading ? '刷新中…' : '刷新'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'providers' && <div className="settings-section">
        <div className="routing-section-header">
          <h3>Provider 管理</h3>
        </div>

        {/* Configured providers only */}
        <div className="provider-list">
          {(providerOverview?.providers || []).length === 0 && (
            <div className="muted" style={{ padding: '12px 0' }}>尚未配置任何 Provider，请在下方添加。</div>
          )}
          {(providerOverview?.providers || []).map((item) => {
            const cp = (providerOverview?.catalog?.providers || []).find((c) => c.provider === item.provider)
            const edit = providerEditMap[item.provider] || {
              display_name: item.display_name || item.provider,
              base_url: item.base_url || '',
              enabled: item.enabled !== false,
              api_key: '',
            }
            return (
              <details key={item.provider} className="provider-row">
                <summary className="provider-summary">
                  <span className="provider-dot configured" />
                  <span className="provider-name">{item.display_name || item.provider}</span>
                  <span className="provider-meta">
                    {(cp?.modes || []).map((m) => m.mode).join(', ')}
                    {cp?.modes?.[0]?.default_model ? ` · ${cp.modes[0].default_model}` : ''}
                  </span>
                  <span className="provider-badge">已配置</span>
                  {item.api_key_masked && <span className="provider-key muted">{item.api_key_masked}</span>}
                </summary>
                <div className="provider-edit">
                  <div className="routing-grid">
                    <div className="routing-field">
                      <label>显示名称</label>
                      <input value={edit.display_name} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, display_name: e.target.value } }))} placeholder={item.provider} />
                    </div>
                    <div className="routing-field">
                      <label>Base URL</label>
                      <input value={edit.base_url} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, base_url: e.target.value } }))} placeholder="留空使用系统默认" />
                    </div>
                    <div className="routing-field">
                      <label>API Key</label>
                      <input type="password" autoComplete="new-password" value={edit.api_key} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, api_key: e.target.value } }))} placeholder="留空不变更" />
                    </div>
                    <div className="routing-field">
                      <label className="toggle">
                        <input type="checkbox" checked={edit.enabled} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, enabled: e.target.checked } }))} />
                        启用
                      </label>
                    </div>
                  </div>
                  <div className="provider-actions">
                    <button type="button" className="secondary-btn" onClick={() => void handleUpdateProvider(item.provider)} disabled={providerBusy || busy}>保存</button>
                    <button type="button" className="secondary-btn" onClick={() => void handleProbeProviderModels(item.provider)} disabled={providerBusy || busy}>探测模型</button>
                    <button type="button" className="ghost" onClick={() => void handleDisableProvider(item.provider)} disabled={providerBusy || busy}>删除配置</button>
                  </div>
                  {providerProbeMap[item.provider] ? <div className="probe-result"><span className="muted" style={{ fontSize: 12 }}>探测结果：</span><span className="probe-chips">{providerProbeMap[item.provider].split('，').map((m, i) => <span key={i} className="probe-chip">{m}</span>)}</span></div> : null}
                </div>
              </details>
            )
          })}
        </div>

        {/* Add provider section */}
        <div className="provider-add-section">
          <div className="provider-add-header">添加 Provider</div>
          {providerAddMode === '' && (
            <div className="provider-preset-group">
              {(() => {
                const configuredIds = new Set((providerOverview?.providers || []).map((p) => p.provider))
                const presets = (providerOverview?.shared_catalog?.providers || []).filter(
                  (p) => !configuredIds.has(p.provider),
                )
                return (
                  <>
                    {presets.map((p) => (
                      <button
                        key={p.provider}
                        type="button"
                        className="provider-preset-btn"
                        onClick={() => {
                          setProviderAddMode('preset')
                          setProviderAddPreset(p.provider)
                          setProviderCreateForm({
                            provider_id: p.provider,
                            display_name: p.provider,
                            base_url: '',
                            api_key: '',
                            enabled: true,
                          })
                        }}
                      >
                        {p.provider}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="provider-preset-btn provider-preset-custom"
                      onClick={() => {
                        setProviderAddMode('custom')
                        setProviderAddPreset('')
                        setProviderCreateForm({
                          provider_id: '',
                          display_name: '',
                          base_url: '',
                          api_key: '',
                          enabled: true,
                        })
                      }}
                    >
                      OpenAI 兼容（自定义）
                    </button>
                  </>
                )
              })()}
            </div>
          )}

          {providerAddMode === 'preset' && (
            <div className="provider-add-form">
              <div className="provider-add-form-title">
                配置 {providerAddPreset}
                <button type="button" className="ghost" onClick={() => { setProviderAddMode(''); setProviderAddPreset('') }}>取消</button>
              </div>
              <div className="routing-grid">
                <div className="routing-field">
                  <label>API Key（必填）</label>
                  <input type="password" autoComplete="new-password" value={providerCreateForm.api_key} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))} placeholder="输入 API Key" />
                </div>
                <div className="routing-field">
                  <label>Base URL（可选）</label>
                  <input
                    value={providerCreateForm.base_url}
                    onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))}
                    placeholder={(() => {
                      const cat = (providerOverview?.shared_catalog?.providers || []).find((p) => p.provider === providerAddPreset)
                      return cat?.base_url || '使用默认地址'
                    })()}
                  />
                </div>
                <div className="routing-field">
                  <label>显示名称（可选）</label>
                  <input value={providerCreateForm.display_name} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))} placeholder={providerAddPreset} />
                </div>
              </div>
              <div className="provider-actions">
                <button type="button" className="secondary-btn" onClick={() => void handleCreateProvider()} disabled={providerBusy || busy}>{providerBusy ? '处理中…' : '添加'}</button>
              </div>
            </div>
          )}

          {providerAddMode === 'custom' && (
            <div className="provider-add-form">
              <div className="provider-add-form-title">
                自定义 Provider
                <button type="button" className="ghost" onClick={() => { setProviderAddMode(''); setProviderAddPreset('') }}>取消</button>
              </div>
              <div className="routing-grid">
                <div className="routing-field">
                  <label>Provider ID（必填）</label>
                  <input value={providerCreateForm.provider_id} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, provider_id: e.target.value }))} placeholder="例如：my_proxy" />
                </div>
                <div className="routing-field">
                  <label>Base URL（必填）</label>
                  <input value={providerCreateForm.base_url} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))} placeholder="https://api.example.com/v1" />
                </div>
                <div className="routing-field">
                  <label>API Key（必填）</label>
                  <input type="password" autoComplete="new-password" value={providerCreateForm.api_key} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))} />
                </div>
                <div className="routing-field">
                  <label>显示名称（可选）</label>
                  <input value={providerCreateForm.display_name} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))} placeholder="例如：主中转" />
                </div>
              </div>
              <div className="provider-actions">
                <button type="button" className="secondary-btn" onClick={() => void handleCreateProvider()} disabled={providerBusy || busy}>{providerBusy ? '处理中…' : '添加'}</button>
              </div>
            </div>
          )}
        </div>
      </div>}

      {activeTab === 'channels' && <div className="settings-section">
        <div className="routing-section-header">
          <h3>渠道配置</h3>
          <button type="button" className="secondary-btn" onClick={addChannel} disabled={busy}>
            新增渠道
          </button>
        </div>
        {draft.channels.length === 0 && <div className="muted">暂无渠道，请先新增。</div>}
        <div className="routing-list">
          {draft.channels.map((channel, index) => {
            const modeOptions = providerModeMap.get(channel.target.provider) || []
            return (
              <div key={`${channel.id}_${index}`} className="routing-item">
                <div className="routing-item-head">
                  <strong>{channel.title || channel.id || `渠道${index + 1}`}</strong>
                  <button type="button" className="ghost" onClick={() => removeChannel(index)} disabled={busy}>
                    删除
                  </button>
                </div>
                <div className="routing-grid">
                  <div className="routing-field">
                    <label>名称</label>
                    <input
                      value={channel.title}
                      onChange={(e) => updateChannel(index, (prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="例如：教师快速"
                    />
                  </div>
                  <div className="routing-field">
                    <label>Provider</label>
                    <select
                      value={channel.target.provider}
                      onChange={(e) => {
                        const nextProvider = e.target.value
                        const nextModes = providerModeMap.get(nextProvider) || []
                        const nextMode = nextModes.includes(channel.target.mode) ? channel.target.mode : nextModes[0] || ''
                        updateChannel(index, (prev) => ({
                          ...prev,
                          target: { ...prev.target, provider: nextProvider, mode: nextMode },
                        }))
                        if (nextProvider) void fetchModels(nextProvider)
                      }}
                    >
                      <option value="">请选择</option>
                      {providers.map((provider) => (
                        <option key={provider.provider} value={provider.provider}>
                          {provider.provider}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="routing-field">
                    <label>模型</label>
                    <ModelCombobox
                      value={channel.target.model}
                      onChange={(val) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          target: { ...prev.target, model: val },
                        }))
                      }
                      models={modelsMap[channel.target.provider]?.models || []}
                      loading={modelsMap[channel.target.provider]?.loading}
                      error={modelsMap[channel.target.provider]?.error}
                      onFocus={() => { if (channel.target.provider) void fetchModels(channel.target.provider) }}
                    />
                  </div>
                </div>
                <details>
                  <summary>高级设置</summary>
                  <div className="routing-grid">
                    <div className="routing-field">
                      <label>渠道 ID</label>
                      <input
                        value={channel.id}
                        onChange={(e) => updateChannel(index, (prev) => ({ ...prev, id: e.target.value }))}
                        placeholder="例如：teacher_fast"
                      />
                    </div>
                    <div className="routing-field">
                      <label>Mode</label>
                      <select
                        value={channel.target.mode}
                        onChange={(e) =>
                          updateChannel(index, (prev) => ({
                            ...prev,
                            target: { ...prev.target, mode: e.target.value },
                          }))
                        }
                      >
                        <option value="">请选择</option>
                        {modeOptions.map((mode) => (
                          <option key={mode} value={mode}>
                            {mode}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="routing-field">
                      <label>temperature</label>
                      <input
                        value={channel.params.temperature ?? ''}
                        onChange={(e) =>
                          updateChannel(index, (prev) => ({
                            ...prev,
                            params: { ...prev.params, temperature: asNumberOrNull(e.target.value) },
                          }))
                        }
                        placeholder="留空表示默认"
                      />
                    </div>
                    <div className="routing-field">
                      <label>max_tokens</label>
                      <input
                        value={channel.params.max_tokens ?? ''}
                        onChange={(e) =>
                          updateChannel(index, (prev) => ({
                            ...prev,
                            params: { ...prev.params, max_tokens: asNumberOrNull(e.target.value) },
                          }))
                        }
                        placeholder="留空表示默认"
                      />
                    </div>
                    <div className="routing-field">
                      <label>回退渠道（逗号分隔）</label>
                      <input
                        value={formatList(channel.fallback_channels || [])}
                        onChange={(e) =>
                          updateChannel(index, (prev) => ({
                            ...prev,
                            fallback_channels: parseList(e.target.value),
                          }))
                        }
                        placeholder="例如：teacher_safe,teacher_backup"
                      />
                    </div>
                    <div className="routing-field">
                      <label>能力</label>
                      <div className="routing-switches">
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={channel.capabilities.tools}
                            onChange={(e) =>
                              updateChannel(index, (prev) => ({
                                ...prev,
                                capabilities: { ...prev.capabilities, tools: e.target.checked },
                              }))
                            }
                          />
                          支持工具调用
                        </label>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={channel.capabilities.json}
                            onChange={(e) =>
                              updateChannel(index, (prev) => ({
                                ...prev,
                                capabilities: { ...prev.capabilities, json: e.target.checked },
                              }))
                            }
                          />
                          支持 JSON 输出
                        </label>
                      </div>
                    </div>
                  </div>
                </details>
              </div>
            )
          })}
        </div>
      </div>}

      {activeTab === 'rules' && <div className="settings-section">
        <div className="routing-section-header">
          <h3>规则配置</h3>
          <button type="button" className="secondary-btn" onClick={addRule} disabled={busy}>
            新增规则
          </button>
        </div>
        <div className="routing-order">命中顺序（按优先级）：{ruleOrderHint || '暂无规则'}</div>
        {draft.rules.length === 0 && <div className="muted">暂无规则，请先新增。</div>}
        <div className="routing-list">
          {draft.rules.map((rule, index) => {
            const channelTitle = draft.channels.find((c) => c.id === rule.route.channel_id)?.title || rule.route.channel_id || '未指定'
            return (
            <div key={`${rule.id}_${index}`} className={`rule-card ${rule.enabled !== false ? 'rule-enabled' : 'rule-disabled'}`}>
              <div className="rule-summary">
                <label className="toggle rule-toggle">
                  <input
                    type="checkbox"
                    checked={rule.enabled !== false}
                    onChange={(e) => updateRule(index, (prev) => ({ ...prev, enabled: e.target.checked }))}
                  />
                </label>
                <span className="rule-name">{rule.id || `规则${index + 1}`}</span>
                <span className="rule-arrow">
                  {formatList(rule.match.roles || []) || '所有角色'} → {channelTitle}
                </span>
                <span className="rule-priority">P{rule.priority}</span>
                <button type="button" className="ghost" onClick={() => removeRule(index)} disabled={busy}>
                  删除
                </button>
              </div>
              <details>
                <summary>编辑规则</summary>
                <div className="routing-grid">
                  <div className="routing-field">
                    <label>规则 ID</label>
                    <input
                      value={rule.id}
                      onChange={(e) => updateRule(index, (prev) => ({ ...prev, id: e.target.value }))}
                      placeholder="例如：teacher_agent"
                    />
                  </div>
                  <div className="routing-field">
                    <label>优先级</label>
                    <input
                      value={rule.priority}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          priority: Number.isFinite(Number(e.target.value)) ? Number(e.target.value) : 0,
                        }))
                      }
                    />
                  </div>
                  <div className="routing-field">
                    <label>角色（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.roles || [])}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, roles: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：teacher,student"
                    />
                  </div>
                  <div className="routing-field">
                    <label>目标渠道</label>
                    <select
                      value={rule.route.channel_id || ''}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          route: { channel_id: e.target.value },
                        }))
                      }
                    >
                      <option value="">请选择</option>
                      {draft.channels.map((channel) => (
                        <option key={channel.id} value={channel.id}>
                          {channel.title || channel.id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="routing-field">
                    <label>技能 ID（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.skills || [])}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, skills: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：physics-homework-generator"
                    />
                  </div>
                  <div className="routing-field">
                    <label>任务类型 kind（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.kinds || [])}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, kinds: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：chat.agent,upload.assignment_parse"
                    />
                  </div>
                  <div className="routing-field">
                    <label>是否必须工具调用</label>
                    <select
                      value={boolMatchValue(rule.match.needs_tools)}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, needs_tools: boolMatchFromValue(e.target.value) },
                        }))
                      }
                    >
                      <option value="any">不限</option>
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </div>
                  <div className="routing-field">
                    <label>是否必须 JSON</label>
                    <select
                      value={boolMatchValue(rule.match.needs_json)}
                      onChange={(e) =>
                        updateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, needs_json: boolMatchFromValue(e.target.value) },
                        }))
                      }
                    >
                      <option value="any">不限</option>
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </div>
                </div>
              </details>
            </div>
            )
          })}
        </div>
      </div>}

      {activeTab === 'simulate' && <div className="settings-section">
        <h3>仿真验证（基于当前草稿）</h3>
        <div className="routing-grid">
          <div className="routing-field">
            <label>角色</label>
            <input value={simRole} onChange={(e) => setSimRole(e.target.value)} placeholder="teacher" />
          </div>
          <div className="routing-field">
            <label>技能 ID</label>
            <input value={simSkillId} onChange={(e) => setSimSkillId(e.target.value)} placeholder="physics-teacher-ops" />
          </div>
          <div className="routing-field">
            <label>任务类型 kind</label>
            <input value={simKind} onChange={(e) => setSimKind(e.target.value)} placeholder="chat.agent" />
          </div>
          <div className="routing-field">
            <label className="toggle">
              <input type="checkbox" checked={simNeedsTools} onChange={(e) => setSimNeedsTools(e.target.checked)} />
              需要工具调用
            </label>
          </div>
          <div className="routing-field">
            <label className="toggle">
              <input type="checkbox" checked={simNeedsJson} onChange={(e) => setSimNeedsJson(e.target.checked)} />
              需要 JSON
            </label>
          </div>
        </div>
        <div className="routing-actions">
          <button type="button" className="secondary-btn" onClick={handleSimulate} disabled={busy}>
            {busy ? '仿真中…' : '运行仿真'}
          </button>
        </div>
        {simResult && (
          <div className="routing-sim-panel">
            <div className="routing-sim-grid">
              <div className="routing-sim-card routing-sim-conclusion-card">
                <h4>仿真结论</h4>
                <div className="routing-sim-kv">
                  <span>命中规则</span>
                  <strong>{simResult.decision?.matched_rule_id || '未命中，走默认回退'}</strong>
                </div>
                <div className="routing-sim-kv">
                  <span>目标模型</span>
                  <strong>
                    {formatTargetLabel(simPrimaryCandidate?.provider, simPrimaryCandidate?.mode, simPrimaryCandidate?.model)}
                  </strong>
                </div>
                <div className="routing-sim-kv">
                  <span>决策状态</span>
                  <strong>{simResult.decision?.selected ? '已选出候选链路' : '未选出候选链路'}</strong>
                </div>
              </div>
              <div className="routing-sim-card">
                <h4>决策原因</h4>
                <p className="routing-sim-reason">{simResult.decision?.reason || '无可用原因信息'}</p>
              </div>
            </div>

            <details className="routing-sim-card routing-sim-candidates">
              <summary>候选链路（{simCandidates.length}）</summary>
              {simCandidates.length === 0 ? (
                <div className="muted">无候选渠道。</div>
              ) : (
                <div className="routing-sim-candidate-list">
                  {simCandidates.map((candidate, index) => (
                    <div key={`${candidate.channel_id}_${index}`} className="routing-sim-candidate-item">
                      <div className="routing-sim-candidate-head">#{index + 1} · {candidate.channel_id || '未命名渠道'}</div>
                      <div className="routing-sim-candidate-target">
                        {formatTargetLabel(candidate.provider, candidate.mode, candidate.model)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </details>

            {simResult.validation?.errors?.length ? (
              <div className="status err">校验错误：{simResult.validation.errors.join('；')}</div>
            ) : null}
            {simResult.validation?.warnings?.length ? (
              <div className="status ok">线上配置提示：{simResult.validation.warnings.join('；')}</div>
            ) : null}
            {simResult.override_validation?.errors?.length ? (
              <div className="status err">草稿校验错误：{simResult.override_validation.errors.join('；')}</div>
            ) : null}
            {simResult.override_validation?.warnings?.length ? (
              <div className="status ok">草稿提示：{simResult.override_validation.warnings.join('；')}</div>
            ) : null}

            <details className="routing-proposal-json">
              <summary>技术详情 JSON</summary>
              <pre>{JSON.stringify(simResult, null, 2)}</pre>
            </details>
          </div>
        )}
      </div>}

      {activeTab === 'history' && <div className="settings-section">
        <h3>提案与回滚</h3>
        <div className="routing-grid">
          <div className="routing-field">
            <label>回滚目标版本</label>
            <input value={rollbackVersion} onChange={(e) => setRollbackVersion(e.target.value)} placeholder="例如：3" />
          </div>
          <div className="routing-field">
            <label>回滚备注（可选）</label>
            <input value={rollbackNote} onChange={(e) => setRollbackNote(e.target.value)} placeholder="例如：线上效果退化，先回退" />
          </div>
        </div>
        <div className="routing-actions">
          <button
            type="button"
            className="secondary-btn"
            onClick={() => {
              const parsed = Number(rollbackVersion)
              void handleRollback(parsed)
            }}
            disabled={busy}
          >
            回滚到指定版本
          </button>
        </div>

        <div className="routing-subsection">
          <div className="routing-section-header">
            <h4>待审核提案（高级）</h4>
            <button type="button" className="ghost" onClick={() => setShowManualReview((prev) => !prev)} disabled={busy}>
              {showManualReview ? '收起' : `展开${pendingProposals.length ? `（${pendingProposals.length}）` : ''}`}
            </button>
          </div>
          {!showManualReview ? (
            <div className="muted">
              单管理员模式默认自动生效，仅在需要处理历史遗留提案时再展开手动审核。
              {pendingProposals.length ? ` 当前有 ${pendingProposals.length} 条待审核提案。` : ''}
            </div>
          ) : (
            <>
              {pendingProposals.length === 0 ? <div className="muted">暂无待审核提案。</div> : null}
              {pendingProposals.map((proposal) => {
                const proposalId = proposal.proposal_id
                const expanded = Boolean(expandedProposalIds[proposalId])
                const loadingDetail = Boolean(proposalLoadingMap[proposalId])
                const detail = proposalDetails[proposalId]
                const validation = detail?.proposal?.validation
                const errors = Array.isArray(validation?.errors) ? validation?.errors : []
                const warnings = Array.isArray(validation?.warnings) ? validation?.warnings : []
                return (
                  <div key={proposalId} className="routing-proposal-block">
                    <div className="routing-row">
                      <div className="routing-row-main">
                        <strong>{proposalId}</strong>
                        <span className="muted"> {proposal.created_at}</span>
                        {proposal.note ? <div className="muted">{proposal.note}</div> : null}
                      </div>
                      <div className="routing-row-actions">
                        <button type="button" className="secondary-btn" onClick={() => void handleToggleProposalDetail(proposalId)} disabled={busy}>
                          {expanded ? '收起详情' : '展开详情'}
                        </button>
                        <button type="button" className="secondary-btn" onClick={() => void handleReviewProposal(proposalId, true)} disabled={busy}>
                          生效
                        </button>
                        <button type="button" className="secondary-btn" onClick={() => void handleReviewProposal(proposalId, false)} disabled={busy}>
                          拒绝
                        </button>
                      </div>
                    </div>
                    {expanded ? (
                      <div className="routing-proposal-detail">
                        {loadingDetail ? <div className="muted">正在加载提案详情…</div> : null}
                        {!loadingDetail && detail?.ok ? (
                          <>
                            <div className="routing-proposal-meta">
                              状态：{String(detail.proposal?.status || proposal.status || 'pending')}
                              {detail.proposal?.created_by ? ` ｜ 创建人：${detail.proposal.created_by}` : ''}
                              {detail.proposal?.reviewed_by ? ` ｜ 审核人：${detail.proposal.reviewed_by}` : ''}
                            </div>
                            {errors.length ? <div className="status err">校验错误：{errors.join('；')}</div> : null}
                            {warnings.length ? <div className="status ok">校验提示：{warnings.join('；')}</div> : null}
                            <details className="routing-proposal-json">
                              <summary>候选配置（JSON）</summary>
                              <pre>{JSON.stringify(detail.proposal?.candidate || {}, null, 2)}</pre>
                            </details>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </>
          )}
        </div>

        <div className="routing-subsection">
          <div className="routing-section-header">
            <h4>历史版本（最近10次）</h4>
            <button type="button" className="ghost" onClick={() => setShowHistoryVersions((prev) => !prev)} disabled={busy}>
              {showHistoryVersions ? '收起' : `展开${history.length ? `（${history.length}）` : ''}`}
            </button>
          </div>
          {!showHistoryVersions ? (
            <div className="muted">
              默认折叠历史版本以保持界面简洁，按需展开查看或回滚。
              {history.length ? ` 当前有 ${history.length} 条历史记录。` : ''}
            </div>
          ) : (
            <>
              {history.length === 0 ? <div className="muted">暂无历史。</div> : null}
              {historyRows.map(({ item, summary, changes }) => (
                <div key={item.file} className="routing-history-card">
                  <div className="routing-row">
                    <div className="routing-row-main">
                      <strong>v{item.version}</strong>
                      <span className="muted"> {item.saved_at}</span>
                      <div className="routing-history-meta">
                        <span>
                          主模型：
                          {formatTargetLabel(summary?.primary_provider, summary?.primary_mode, summary?.primary_model)}
                        </span>
                        <span>规则 {summary?.rule_count ?? '-'} · 渠道 {summary?.channel_count ?? '-'}</span>
                      </div>
                      <div className="routing-change-title">变更摘要</div>
                      <div className="routing-change-list">
                        {changes.map((change, index) => (
                          <div key={`${item.file}_${index}`} className="routing-change-item">{change}</div>
                        ))}
                      </div>
                      {item.note ? <div className="muted">备注：{item.note}</div> : null}
                    </div>
                    <div className="routing-row-actions">
                      <button type="button" className="secondary-btn" onClick={() => void handleRollback(item.version)} disabled={busy}>
                        回滚到此版本
                      </button>
                    </div>
                  </div>
                  <details className="routing-proposal-json">
                    <summary>查看配置 JSON</summary>
                    <pre>{JSON.stringify(item.config || { summary: summary || null, source: item.source, saved_by: item.saved_by }, null, 2)}</pre>
                  </details>
                </div>
              ))}
            </>
          )}
        </div>
      </div>}

      {['general', 'providers', 'channels', 'rules'].includes(activeTab) && (
        <div className="routing-action-bar">
          <div className="routing-action-bar-left">
            {hasLocalEdits && <span className="routing-draft-indicator">草稿已修改</span>}
            <input
              className="routing-proposal-note"
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="变更备注（可选）"
            />
          </div>
          <div className="routing-action-bar-right">
            <button type="button" className="secondary-btn" onClick={handleResetDraft} disabled={!hasLocalEdits || busy}>
              重置草稿
            </button>
            <button type="button" className="secondary-btn" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '保存并生效'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
