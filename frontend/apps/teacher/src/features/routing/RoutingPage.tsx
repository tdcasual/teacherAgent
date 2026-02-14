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
import RoutingChannelsSection from './RoutingChannelsSection'
import RoutingHistorySection from './RoutingHistorySection'
import RoutingProvidersSection from './RoutingProvidersSection'
import RoutingRulesSection from './RoutingRulesSection'
import RoutingSimulateSection from './RoutingSimulateSection'
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
  /** Legacy compatibility mode: render all routing/provider panels in one page */
  legacyFlat?: boolean
}

const makeId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`

const parseList = (value: string) =>
  value
    .split(/[，,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const formatList = (items: string[]) => items.join('，')

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

export default function RoutingPage({ apiBase, onApiBaseChange, onDirtyChange, section, legacyFlat }: Props) {
  const isLegacyFlat = Boolean(legacyFlat)
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
    default_model: '',
    enabled: true,
  })
  const [providerEditMap, setProviderEditMap] = useState<
    Record<string, { display_name: string; base_url: string; enabled: boolean; api_key: string; default_model: string }>
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

        try {
          const data = await fetchRoutingOverview(apiBase, {
            teacher_id: teacherId || undefined,
            history_limit: 40,
            proposal_limit: 40,
          })
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
    const next: Record<string, { display_name: string; base_url: string; enabled: boolean; api_key: string; default_model: string }> = {}
    ;(providerOverview?.providers || []).forEach((item) => {
      next[item.provider] = {
        display_name: item.display_name || '',
        base_url: item.base_url || '',
        enabled: item.enabled !== false,
        api_key: '',
        default_model: item.default_model || '',
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
        default_model: providerCreateForm.default_model.trim() || undefined,
        enabled: providerCreateForm.enabled,
      })
      if (!result.ok) throw new Error(result.error ? String(result.error) : '新增失败')
      setProviderCreateForm({
        provider_id: '',
        display_name: '',
        base_url: '',
        api_key: '',
        default_model: '',
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
        default_model?: string
      } = {
        teacher_id: teacherId || undefined,
        display_name: draftForm.display_name.trim() || undefined,
        enabled: Boolean(draftForm.enabled),
      }
      payload.base_url = draftForm.base_url.trim()
      payload.default_model = draftForm.default_model.trim() || undefined
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

      if (isLegacyFlat) {
        setStatus(`提案已创建：${proposalId}`)
        setProposalNote('')
        setShowManualReview(true)
        await loadOverview({ silent: true })
        return
      }

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

  const ruleOrderHint = draft.rules
    .slice()
    .sort((a, b) => (b.priority || 0) - (a.priority || 0))
    .map((rule) => `${rule.id || '未命名'}(${rule.priority})`)
    .join(' -> ')

  return (
    <div className="routing-page grid gap-3">
      {isLegacyFlat && <h2>模型路由配置</h2>}
      {status && <div className="status ok">{status}</div>}
      {error && <div className="status err">{error}</div>}

      <div className="routing-current-card border border-[#d9e8e2] rounded-[14px] p-3 grid gap-[10px]" style={{ background: 'linear-gradient(135deg, #fcfffe 0%, #f4fbf8 100%)' }}>
        <div className="flex items-start justify-between gap-[10px] flex-wrap">
          <div className="grid gap-[2px]">
            <h3 className="m-0">当前生效配置</h3>
            <span className="text-[12px] text-muted">先看结论：当前实际生效的规则、渠道与模型</span>
          </div>
          <span className={`inline-flex items-center px-2 py-[3px] rounded-full text-[12px] font-semibold border ${liveStatusTone === 'ok' ? 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]' : liveStatusTone === 'warn' ? 'bg-[#fff7ed] text-[#9a3412] border-[#fed7aa]' : 'bg-[#fef2f2] text-[#b91c1c] border-[#fecaca]'}`}>{loading ? '加载中' : liveStatusText}</span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2">
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">生效规则</span>
            <strong className="text-[13px] leading-[1.35] break-words">{livePrimaryRule?.id || '默认回退'}</strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">主渠道</span>
            <strong className="text-[13px] leading-[1.35] break-words">{livePrimaryChannel?.title || livePrimaryChannel?.id || '未配置'}</strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">目标模型</span>
            <strong className="text-[13px] leading-[1.35] break-words">
              {formatTargetLabel(
                livePrimaryChannel?.target?.provider,
                livePrimaryChannel?.target?.mode,
                livePrimaryChannel?.target?.model,
              )}
            </strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">版本 / 更新时间</span>
            <strong className="text-[13px] leading-[1.35] break-words">
              v{liveRouting?.version || '-'} / {liveRouting?.updated_at || '—'}
            </strong>
          </div>
        </div>
      </div>

      {(activeTab === 'general' || isLegacyFlat) && (
        <div className="settings-section">
          <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(180px,1fr))]">
            <div className="grid gap-[6px]">
              <label>API Base</label>
              <input
                value={apiBase}
                onChange={(e) => onApiBaseChange?.(e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>
            <div className="grid gap-[6px]">
              <label>教师标识（可选）</label>
              <input value={teacherId} onChange={(e) => handleTeacherIdChange(e.target.value)} placeholder="默认 teacher" />
            </div>
            <div className="grid gap-[6px]">
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
          <div className="flex gap-4 flex-wrap text-[12px] text-muted">
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
          <div className="flex gap-2 flex-wrap">
            <button type="button" className="secondary-btn" onClick={() => void loadOverview()} disabled={loading || busy}>
              {loading ? '刷新中…' : '刷新'}
            </button>
          </div>
        </div>
      )}

      {(activeTab === 'providers' || isLegacyFlat) && (
        <RoutingProvidersSection
          isLegacyFlat={isLegacyFlat}
          providerOverview={providerOverview}
          providerEditMap={providerEditMap}
          providerProbeMap={providerProbeMap}
          providerCreateForm={providerCreateForm}
          providerAddMode={providerAddMode}
          providerAddPreset={providerAddPreset}
          providerBusy={providerBusy}
          busy={busy}
          setProviderEditMap={setProviderEditMap}
          setProviderCreateForm={setProviderCreateForm}
          setProviderAddMode={setProviderAddMode}
          setProviderAddPreset={setProviderAddPreset}
          onCreateProvider={() => {
            void handleCreateProvider()
          }}
          onUpdateProvider={(providerId) => {
            void handleUpdateProvider(providerId)
          }}
          onDisableProvider={(providerId) => {
            void handleDisableProvider(providerId)
          }}
          onProbeProviderModels={(providerId) => {
            void handleProbeProviderModels(providerId)
          }}
        />
      )}

      {(activeTab === 'channels' || isLegacyFlat) && (
        <RoutingChannelsSection
          draft={draft}
          busy={busy}
          providers={providers}
          providerModeMap={providerModeMap}
          modelsMap={modelsMap}
          onFetchModels={fetchModels}
          onAddChannel={addChannel}
          onRemoveChannel={removeChannel}
          onUpdateChannel={updateChannel}
          formatList={formatList}
          parseList={parseList}
        />
      )}

      {(activeTab === 'rules' || isLegacyFlat) && (
        <RoutingRulesSection
          draft={draft}
          busy={busy}
          ruleOrderHint={ruleOrderHint}
          onAddRule={addRule}
          onRemoveRule={removeRule}
          onUpdateRule={updateRule}
          formatList={formatList}
          parseList={parseList}
          boolMatchValue={boolMatchValue}
          boolMatchFromValue={boolMatchFromValue}
        />
      )}

      {(activeTab === 'simulate' || isLegacyFlat) && (
        <RoutingSimulateSection
          isLegacyFlat={isLegacyFlat}
          busy={busy}
          simRole={simRole}
          simSkillId={simSkillId}
          simKind={simKind}
          simNeedsTools={simNeedsTools}
          simNeedsJson={simNeedsJson}
          simResult={simResult}
          onSimRoleChange={setSimRole}
          onSimSkillIdChange={setSimSkillId}
          onSimKindChange={setSimKind}
          onSimNeedsToolsChange={setSimNeedsTools}
          onSimNeedsJsonChange={setSimNeedsJson}
          onSimulate={() => {
            void handleSimulate()
          }}
          formatTargetLabel={formatTargetLabel}
        />
      )}

      {(activeTab === 'history' || isLegacyFlat) && (
        <RoutingHistorySection
          isLegacyFlat={isLegacyFlat}
          busy={busy}
          rollbackVersion={rollbackVersion}
          rollbackNote={rollbackNote}
          pendingProposals={pendingProposals}
          showManualReview={showManualReview}
          expandedProposalIds={expandedProposalIds}
          proposalLoadingMap={proposalLoadingMap}
          proposalDetails={proposalDetails}
          showHistoryVersions={showHistoryVersions}
          history={history}
          historyRows={historyRows}
          formatTargetLabel={formatTargetLabel}
          onRollbackVersionChange={setRollbackVersion}
          onRollbackNoteChange={setRollbackNote}
          onRollback={(targetVersion) => {
            void handleRollback(targetVersion)
          }}
          onToggleManualReview={() => setShowManualReview((prev) => !prev)}
          onToggleProposalDetail={(proposalId) => {
            void handleToggleProposalDetail(proposalId)
          }}
          onReviewProposal={(proposalId, approve) => {
            void handleReviewProposal(proposalId, approve)
          }}
          onToggleHistoryVersions={() => setShowHistoryVersions((prev) => !prev)}
        />
      )}

      {(!isLegacyFlat && ['general', 'providers', 'channels', 'rules'].includes(activeTab)) && (
        <div className="sticky bottom-0 flex items-center justify-between gap-3 px-[14px] py-[10px] border-t border-border rounded-[12px] z-[5]" style={{ background: 'rgba(255,255,255,0.94)', backdropFilter: 'saturate(180%) blur(8px)' }}>
          <div className="flex items-center gap-[10px] flex-1 min-w-0">
            {hasLocalEdits && <span className="text-[12px] text-accent font-semibold whitespace-nowrap">草稿已修改</span>}
            <input
              className="max-w-[280px] px-[10px] py-[7px] text-[13px]"
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="变更备注（可选）"
            />
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button type="button" className="secondary-btn" onClick={handleResetDraft} disabled={!hasLocalEdits || busy}>
              重置草稿
            </button>
            <button type="button" className="secondary-btn" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '保存并生效'}
            </button>
          </div>
        </div>
      )}

      {isLegacyFlat && (
        <div className="sticky bottom-0 flex items-center justify-between gap-3 px-[14px] py-[10px] border-t border-border rounded-[12px] z-[5]" style={{ background: 'rgba(255,255,255,0.94)', backdropFilter: 'saturate(180%) blur(8px)' }}>
          <div className="flex items-center gap-[10px] flex-1 min-w-0">
            {hasLocalEdits && <span className="text-[12px] text-accent font-semibold whitespace-nowrap">草稿已修改</span>}
            <input
              className="max-w-[280px] px-[10px] py-[7px] text-[13px]"
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="变更备注（可选）"
            />
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button type="button" className="secondary-btn" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '提交提案'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
